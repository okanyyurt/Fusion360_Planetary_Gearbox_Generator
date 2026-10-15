"""
Autodesk Fusion 360 Planetary Gearbox Generator — Add-In entry point.

The palette shows the same UI as the standalone desktop app. Design, automatic sizing and the
engineering checks run inside Fusion (pure Python `core/`); the geometry is produced by the shared
OpenCascade engine in a separate Python process and imported into the active design as a STEP
assembly. STL files, the engineering report and the parts list are written next to it.

Author: Okan Yeşilyurt & Antigravity
Version: 2.8.0
"""
import json
import os
import sys
import traceback

current_dir = os.path.dirname(os.path.realpath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    import adsk.core
    import adsk.fusion
    HTMLEventHandler = adsk.core.HTMLEventHandler
    UserInterfaceGeneralEventHandler = adsk.core.UserInterfaceGeneralEventHandler
    CommandCreatedEventHandler = adsk.core.CommandCreatedEventHandler
except ImportError:
    adsk = None
    HTMLEventHandler = object
    UserInterfaceGeneralEventHandler = object
    CommandCreatedEventHandler = object

app = None
ui = None
handlers = []
api = None
palette_id = 'PlanetaryGearboxPalette_v3'
cmd_id = 'PlanetaryGearboxCmd_v1'
panel_id = 'PlanetaryGearboxPanel'          # own panel in the UTILITIES tab (like other gear add-ins)
TOOLS_TAB = 'ToolsTab'                      # UTILITIES tab of the Design workspace
CREATE_PANEL = 'SolidCreatePanel'           # SOLID > CREATE menu (secondary entry)
PALETTE_SIZE = (700, 820)                   # fits 1080p screens at 125 % display scaling
kinematics = None


OWN_PACKAGES = ('core', 'standalone', 'occ_cad', 'fusion_kinematics')


def _purge_own_modules():
    """
    Fusion keeps every imported module alive between add-in restarts, so Stop/Run would keep running
    the old design engine after an update. Drop our own modules (only those loaded from this folder)
    so the next import reads the current files.
    """
    root = os.path.normcase(os.path.realpath(current_dir))
    for name in list(sys.modules):
        if name.split('.')[0] not in OWN_PACKAGES:
            continue
        path = getattr(sys.modules.get(name), '__file__', None) or ''
        if path and os.path.normcase(os.path.realpath(path)).startswith(root):
            del sys.modules[name]


def _push_to_palette(data):
    palette = ui.palettes.itemById(palette_id) if ui else None
    if palette:
        palette.sendInfoToHTML('fusionMessageReceived', json.dumps(data, ensure_ascii=False))
        adsk.doEvents()


def _import_step(step_path, name, result=None):
    """Imports the STEP assembly into the active design, then adds joints and motion links."""
    global kinematics
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        raise RuntimeError('Lütfen önce aktif bir Fusion 360 tasarım belgesi açın.')
    before = set(o.fullPathName for o in design.rootComponent.allOccurrences)
    manager = app.importManager
    options = manager.createSTEPImportOptions(step_path)
    if not manager.importToTarget(options, design.rootComponent):
        raise RuntimeError('STEP içe aktarılamadı: ' + step_path)
    try:
        app.activeViewport.fit()
    except Exception:
        pass
    kin = (result or {}).get('kinematics')
    if not kin:
        return None
    from fusion_kinematics import GearboxKinematics
    k = GearboxKinematics()
    kinematics = k
    try:
        k.match(design, before, kin)          # parça grupları (göster/gizle) eklemlerden bağımsız çalışır
        return k.setup(design, before, kin)
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def _rotate(input_deg):
    if kinematics is None:
        raise RuntimeError('Hareket bağlantıları kurulmadı.')
    kinematics.rotate(input_deg)
    adsk.doEvents()


def _set_group_visible(group, on):
    if kinematics is None:
        raise RuntimeError('Önce modeli oluşturun.')
    kinematics.set_group_visible(group, on)
    adsk.doEvents()


def _get_api():
    global api
    if api is None:
        from standalone.fusion_api import FusionApi
        api = FusionApi(push=_push_to_palette, pump=adsk.doEvents, importer=_import_step, rotator=_rotate,
                        visibility=_set_group_visible, addin_dir=current_dir)
    return api


def _api_methods():
    from standalone.fusion_api import FUSION_METHODS
    return FUSION_METHODS


class PaletteHTMLEventHandler(HTMLEventHandler):
    """JS -> Python: adsk.fusionSendData('api', {method, args}); the answer goes back via returnData."""
    def __init__(self):
        super().__init__()

    def notify(self, args):
        html_args = adsk.core.HTMLEventArgs.cast(args)
        try:
            if html_args.action != 'api':
                return
            request = json.loads(html_args.data or '{}')
            method = request.get('method')
            if method not in _api_methods():
                html_args.returnData = json.dumps({'success': False, 'error': 'unknown method: %s' % method})
                return
            result = getattr(_get_api(), method)(*request.get('args', []))
            html_args.returnData = json.dumps(result, ensure_ascii=False, default=str)
        except Exception as e:
            html_args.returnData = json.dumps({'success': False, 'error': str(e)})
            if ui:
                ui.messageBox('Eklenti hatası: %s\n\n%s' % (e, traceback.format_exc()), 'Hata')


class PaletteClosedHandler(UserInterfaceGeneralEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        pass


def show_palette():
    """Creates and displays the HTML5 UI palette."""
    global app, ui
    app = adsk.core.Application.get()
    ui = app.userInterface
    palette = ui.palettes.itemById(palette_id)
    if palette:
        palette.isVisible = True
        return
    html_file_path = os.path.join(current_dir, 'ui', 'index.html')
    if not os.path.exists(html_file_path):
        ui.messageBox('Arayüz dosyası bulunamadı:\n%s' % html_file_path, 'Dosya Hatası')
        return
    # ?host=fusion: arayüz, Fusion'un `adsk` nesnesi geç enjekte edilse bile hemen motor moduna geçer
    from standalone.api import VERSION
    html_url = 'file:///' + html_file_path.replace('\\', '/') + '?host=fusion&v=' + VERSION
    title = 'Planet Redüktör Tasarımcısı (Planetary Gearbox)'
    try:
        # son argüman: Qt tarayıcısı (Autodesk'in önerdiği; fusionSendData Promise döndürür, arayüz donmaz)
        palette = ui.palettes.add(palette_id, title, html_url, True, True, True, *PALETTE_SIZE, True)
    except TypeError:
        palette = ui.palettes.add(palette_id, title, html_url, True, True, True, *PALETTE_SIZE)
    palette.dockingState = adsk.core.PaletteDockingStates.PaletteDockStateFloating
    on_html_event = PaletteHTMLEventHandler()
    palette.incomingFromHTML.add(on_html_event)
    handlers.append(on_html_event)
    on_closed = PaletteClosedHandler()
    palette.closed.add(on_closed)
    handlers.append(on_closed)


class ShowPaletteCommandHandler(CommandCreatedEventHandler):
    """Toolbar button: shows the palette."""
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            show_palette()
        except Exception as e:
            if ui:
                ui.messageBox('Komut Hatası: %s' % e, 'Hata')


def _tools_tab():
    ws = ui.workspaces.itemById('FusionSolidEnvironment')
    return ws.toolbarTabs.itemById(TOOLS_TAB) if ws else None


def _add_toolbar_buttons(cmd_def):
    """UTILITIES tab: own panel with a large (promoted) button; SOLID > CREATE: menu entry."""
    tab = _tools_tab()
    if tab:
        panel = tab.toolbarPanels.itemById(panel_id)
        if not panel:
            panel = tab.toolbarPanels.add(panel_id, 'PLANET REDÜKTÖR', 'SolidScriptsAddinsPanel', False)
        ctrl = panel.controls.itemById(cmd_id) or panel.controls.addCommand(cmd_def)
        ctrl.isPromoted = True
        ctrl.isPromotedByDefault = True
    else:                                         # older Fusion: the ADD-INS panel of UTILITIES
        addins = ui.allToolbarPanels.itemById('SolidScriptsAddinsPanel')
        if addins and not addins.controls.itemById(cmd_id):
            ctrl = addins.controls.addCommand(cmd_def)
            ctrl.isPromoted = True
    create = ui.allToolbarPanels.itemById(CREATE_PANEL)
    if create and not create.controls.itemById(cmd_id):
        create.controls.addCommand(cmd_def)


def _remove_toolbar_buttons():
    tab = _tools_tab()
    if tab:
        panel = tab.toolbarPanels.itemById(panel_id)
        if panel:
            panel.deleteMe()
    for pid in ('SolidScriptsAddinsPanel', CREATE_PANEL):
        panel = ui.allToolbarPanels.itemById(pid)
        ctrl = panel.controls.itemById(cmd_id) if panel else None
        if ctrl:
            ctrl.deleteMe()


def run(context):
    """Fusion 360 add-in start."""
    global app, ui
    try:
        _purge_own_modules()
        app = adsk.core.Application.get()
        ui = app.userInterface
        show_palette()
        cmd_defs = ui.commandDefinitions
        old = cmd_defs.itemById(cmd_id)
        if old:                                   # leftover of an older version (maybe without an icon)
            old.deleteMe()
        cmd_def = cmd_defs.addButtonDefinition(
            cmd_id, 'Planet Redüktör',
            'Planet redüktör tasarımcısını açar: otomatik boyutlandırma, mühendislik hesabı, AI asistan, '
            'baskıya hazır STEP/STL.', os.path.join(current_dir, 'resources', 'planetary'))
        on_cmd_created = ShowPaletteCommandHandler()
        cmd_def.commandCreated.add(on_cmd_created)
        handlers.append(on_cmd_created)
        _add_toolbar_buttons(cmd_def)
    except Exception as e:
        if ui:
            ui.messageBox('Başlatma Hatası: %s\n\n%s' % (e, traceback.format_exc()), 'Eklenti Hatası')


def stop(context):
    """Fusion 360 add-in stop / cleanup."""
    global api
    try:
        if ui:
            palette = ui.palettes.itemById(palette_id)
            if palette:
                palette.deleteMe()
            _remove_toolbar_buttons()
            cmd_def = ui.commandDefinitions.itemById(cmd_id)
            if cmd_def:
                cmd_def.deleteMe()
        handlers.clear()
        api = None
        _purge_own_modules()
    except Exception:
        pass
