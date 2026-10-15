"""
Fusion 360: kinematic setup of the imported gearbox (runs inside Fusion only).

After the STEP assembly is imported, every component occurrence is matched to the engine's
kinematic table (component name + position). Then:
  * fixed parts (housing, flange, cover, bolts, output bearing) are grounded,
  * the members of every rigid body (carrier plates + pins + spacers, planet + its bearings) are
    put in a rigid group,
  * revolute as-built joints are added: input sun and carriers about the main axis (to ground),
    each planet about its own axis (to its carrier),
  * motion links tie every joint to the input joint with the exact gear ratio, so dragging one
    gear in the viewport turns the whole train.
`rotate(angle)` drives the joints from the palette slider.
"""
import math

import adsk.core
import adsk.fusion

MM = 0.1   # Fusion internal unit is cm


def _leaf_occurrences(root, before_paths):
    out = []
    for occ in root.allOccurrences:
        if occ.fullPathName in before_paths:
            continue
        if occ.bRepBodies.count > 0:
            out.append(occ)
    return out


def _center(occ):
    bb = occ.boundingBox
    return ((bb.minPoint.x + bb.maxPoint.x) / 2.0, (bb.minPoint.y + bb.maxPoint.y) / 2.0,
            (bb.minPoint.z + bb.maxPoint.z) / 2.0)


def _base_name(name):
    name = name.split(':')[0].strip()
    if name.endswith(')') and ' (' in name:
        name = name[:name.rfind(' (')]
    return name


def _match(occurrences, items):
    """Occurrence -> kinematic item, by component name and nearest position."""
    free = list(items)
    result = []
    for occ in occurrences:
        cx, cy, cz = _center(occ)
        name = _base_name(occ.component.name)
        cands = [it for it in free if it["name"] == name] or free
        if not cands:
            continue
        best = min(cands, key=lambda it: (it["center"][0] * MM - cx) ** 2 + (it["center"][1] * MM - cy) ** 2 +
                   (it["center"][2] * MM - cz) ** 2)
        free.remove(best)
        result.append((occ, best))
    return result


def _axis_edge(occ, cx, cy):
    """Circular edge of the occurrence whose center lies on the axis (cx, cy) [cm] and is parallel to Z."""
    best, best_r, sign = None, -1.0, 1.0
    for body in occ.bRepBodies:
        for edge in body.edges:
            g = edge.geometry
            if g.curveType not in (adsk.core.Curve3DTypes.Circle3DCurveType, adsk.core.Curve3DTypes.Arc3DCurveType):
                continue
            n, c = g.normal, g.center
            if abs(abs(n.z) - 1.0) > 1e-6 or math.hypot(c.x - cx, c.y - cy) > 1e-3:
                continue
            if g.radius > best_r:
                best, best_r, sign = edge, g.radius, (1.0 if n.z > 0 else -1.0)
    return best, sign


class GearboxKinematics:
    def __init__(self):
        self.joints = {}      # body -> (joint, sign)
        self.bodies = {}
        self.links = 0
        self.input_body = 'input'
        self.matched = []     # (occurrence, kinematic item)
        self.groups = {}      # part group -> occurrences (palette show/hide)

    def match(self, design, before_paths, kin):
        """Imported occurrences -> kinematic items; also builds the part groups for show/hide."""
        self.matched = _match(_leaf_occurrences(design.rootComponent, before_paths), kin['items'])
        self.groups = {}
        for occ, item in self.matched:
            self.groups.setdefault(item.get('group', ''), []).append(occ)
        return len(self.matched)

    def set_group_visible(self, group, on):
        for occ in self.groups.get(group, []):
            try:
                occ.isLightBulbOn = bool(on)
            except Exception:
                pass

    def setup(self, design, before_paths, kin):
        root = design.rootComponent
        if design.designType != adsk.fusion.DesignTypes.ParametricDesignType:
            raise RuntimeError('Hareket için tasarım geçmişi (parametrik mod) açık olmalı.')
        self.bodies = kin['bodies']
        self.input_body = kin.get('input', 'input')
        matched = self.matched or _match(_leaf_occurrences(root, before_paths), kin['items'])
        members = {}
        for occ, item in matched:
            members.setdefault(item['body'], []).append((occ, item))
        ground = members.get('ground', [])
        if not ground:
            raise RuntimeError('Sabit gövde bileşenleri bulunamadı.')
        for occ, _ in ground:
            occ.isGrounded = True
        ground_occ = max(ground, key=lambda m: m[1]['volume'])[0]

        leads = {}
        for body, ms in members.items():
            if body == 'ground':
                continue
            ms.sort(key=lambda m: -m[1]['volume'])
            leads[body] = ms[0][0]
            if len(ms) > 1:
                coll = adsk.core.ObjectCollection.create()
                for occ, _ in ms:
                    coll.add(occ)
                root.rigidGroups.add(coll, False)

        joints = root.asBuiltJoints
        order = sorted(leads, key=lambda b: (self.bodies[b]['type'] == 'planet', b))
        for body in order:
            spec = self.bodies[body]
            occ = leads[body]
            if spec['type'] == 'planet':
                cx, cy = spec['center'][0] * MM, spec['center'][1] * MM
                # a fixed carrier (rotating housing output): the planet turns about its axis against ground
                other = ground_occ if spec['carrier'] == 'ground' else leads.get(spec['carrier'])
            else:
                cx, cy, other = 0.0, 0.0, ground_occ
            edge, sign = _axis_edge(occ, cx, cy)
            if edge is None or other is None:
                continue
            geo = adsk.fusion.JointGeometry.createByCurve(edge, adsk.fusion.JointKeyPointTypes.CenterKeyPoint)
            inp = joints.createInput(occ, other, geo)
            inp.setAsRevoluteJointMotion(adsk.fusion.JointDirections.ZAxisJointDirection)
            joint = joints.add(inp)
            joint.name = 'PG_' + body
            self.joints[body] = (joint, sign)

        if self.input_body not in self.joints:
            raise RuntimeError('Giriş güneşi için eklem kurulamadı.')
        j0, s0 = self.joints[self.input_body]
        for body, (joint, sb) in self.joints.items():
            if body == self.input_body:
                continue
            spec = self.bodies[body]
            ratio = spec['factor'] if spec['type'] == 'axis' else spec['spin']
            k = ratio * sb * s0
            try:
                li = root.motionLinks.createInput(j0, joint)
                li.valueOne = adsk.core.ValueInput.createByString('360 deg')
                li.valueTwo = adsk.core.ValueInput.createByString('%.6f deg' % (abs(k) * 360.0))
                li.isReversed = k < 0
                if root.motionLinks.add(li):
                    self.links += 1
            except Exception:
                pass
        return {'ok': True, 'joints': len(self.joints), 'links': self.links}

    def rotate(self, input_deg):
        if not self.joints:
            raise RuntimeError('Hareket bağlantıları kurulmadı.')
        theta = math.radians(input_deg)
        if self.links == len(self.joints) - 1:
            joint, sign = self.joints[self.input_body]
            joint.jointMotion.rotationValue = theta * sign
            return
        for body, (joint, sign) in self.joints.items():
            spec = self.bodies[body]
            ratio = spec['factor'] if spec['type'] == 'axis' else spec['spin']
            joint.jointMotion.rotationValue = ratio * theta * sign
