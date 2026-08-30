"""
Autodesk Fusion 360 Planetary Gearbox Generator
Main Add-In / Script Entry Point.

Creates the Fusion 360 Ribbon Command, launches the interactive HTML5 Palette UI,
handles JavaScript bi-directional events, and drives 3D CAD modeling.

Author: Okan Yeşilyurt & Antigravity
Version: 1.0.0
"""
import os
import sys
import json
import traceback

# Add current folder to sys.path so core and cad modules are resolved properly
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

from cad.assembly_manager import PlanetaryAssemblyManager

# Global references to keep handlers alive in memory
app = None
ui = None
handlers = []
palette_id = 'PlanetaryGearboxPalette_v1'
cmd_id = 'PlanetaryGearboxCmd_v1'

class PaletteHTMLEventHandler(HTMLEventHandler):
    """Handles incoming data/events from JavaScript inside the HTML Palette."""
    def __init__(self):
        super().__init__()
        
    def notify(self, args: adsk.core.HTMLEventArgs):
        try:
            html_args = adsk.core.HTMLEventArgs.cast(args)
            action = html_args.action
            data_str = html_args.data
            
            if action == 'generateGearbox':
                payload = json.loads(data_str)
                
                # Check active design
                product = app.activeProduct
                design = adsk.fusion.Design.cast(product)
                if not design:
                    ui.messageBox('Lütfen önce aktif bir Fusion 360 tasarım belgesi (.f3d) açın.', 'Belge Bulunamadı')
                    return
                
                # Run CAD Generation
                success = PlanetaryAssemblyManager.generate_gearbox(payload)
                if success:
                    ui.messageBox(
                        f"Planet Redüktör Başarıyla Oluşturuldu!\n\n"
                        f"• Toplam Oran: {payload.get('total_ratio')}:1\n"
                        f"• Kademe Sayısı: {len(payload.get('stages', []))}\n"
                        f"• Diş Tipi: {'Balıksırtı (Herringbone)' if payload.get('is_herringbone') else 'Düz (Spur)'}\n"
                        f"• Motor Şaftı: Ø{payload.get('motor_shaft_dia')} mm ({payload.get('motor_shaft_type')})",
                        "İşlem Tamamlandı"
                    )
                else:
                    ui.messageBox("Modelleme sırasında bir hata oluştu.", "Hata")
                    
        except Exception as e:
            if ui:
                ui.messageBox(f"HTML Event Hatası: {str(e)}\n\n{traceback.format_exc()}", "Hata")

class PaletteClosedHandler(UserInterfaceGeneralEventHandler):
    """Handles palette close event."""
    def __init__(self):
        super().__init__()
    def notify(self, args):
        pass

def show_palette():
    """Creates and displays the HTML5 UI Palette."""
    global app, ui
    app = adsk.core.Application.get()
    ui = app.userInterface
    
    # Check if palette already exists
    palette = ui.palettes.itemById(palette_id)
    if palette:
        palette.isVisible = True
        return
        
    # HTML File path
    html_file_path = os.path.join(current_dir, 'ui', 'index.html')
    if not os.path.exists(html_file_path):
        ui.messageBox(f"Arayüz dosyası bulunamadı:\n{html_file_path}", "Dosya Hatası")
        return
        
    html_url = 'file:///' + html_file_path.replace('\\', '/')
    
    # Create Palette (Width: 620px, Height: 750px)
    palette = ui.palettes.add(
        palette_id,
        'Planet Redüktör Tasarımcısı (Planetary Gearbox)',
        html_url,
        True,  # isVisible
        True,  # showCloseButton
        True,  # isResizable
        640,
        780
    )
    palette.dockingState = adsk.core.PaletteDockingStates.PaletteDockStateFloating
    
    # Register HTML Event Handler
    on_html_event = PaletteHTMLEventHandler()
    palette.incomingFromHTML.add(on_html_event)
    handlers.append(on_html_event)
    
    on_closed = PaletteClosedHandler()
    palette.closed.add(on_closed)
    handlers.append(on_closed)

class CommandCreatedEventHandler(CommandCreatedEventHandler):
    """Handles toolbar button click to show the UI."""
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            show_palette()
        except Exception as e:
            if ui:
                ui.messageBox(f"Komut Hatası: {str(e)}", "Hata")

def run(context):
    """Fusion 360 Add-in Start entry point."""
    global app, ui
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        
        # When executed directly as a script, open the palette immediately
        show_palette()
        
        # Also register a ribbon button under CREATE panel
        cmd_defs = ui.commandDefinitions
        cmd_def = cmd_defs.itemById(cmd_id)
        if not cmd_def:
            cmd_def = cmd_defs.addButtonDefinition(
                cmd_id,
                'Planet Redüktör Oluşturucu',
                'Parametrik çok kademeli balıksırtı ve düz planet dişli redüktör çizer.',
                ''
            )
            
        on_cmd_created = CommandCreatedEventHandler()
        cmd_def.commandCreated.add(on_cmd_created)
        handlers.append(on_cmd_created)
        
        # Add to SOLID > CREATE panel
        solid_panel = ui.allToolbarPanels.itemById('SolidCreatePanel')
        if solid_panel:
            btn_ctrl = solid_panel.controls.itemById(cmd_id)
            if not btn_ctrl:
                solid_panel.controls.addCommand(cmd_def)
                
    except Exception as e:
        if ui:
            ui.messageBox(f"Başlatma Hatası: {str(e)}\n\n{traceback.format_exc()}", "Eklenti Hatası")

def stop(context):
    """Fusion 360 Add-in Stop / Cleanup entry point."""
    global app, ui
    try:
        if ui:
            # Remove Palette
            palette = ui.palettes.itemById(palette_id)
            if palette:
                palette.deleteMe()
                
            # Remove Toolbar Button Control
            solid_panel = ui.allToolbarPanels.itemById('SolidCreatePanel')
            if solid_panel:
                btn_ctrl = solid_panel.controls.itemById(cmd_id)
                if btn_ctrl:
                    btn_ctrl.deleteMe()
                    
            # Remove Command Definition
            cmd_def = ui.commandDefinitions.itemById(cmd_id)
            if cmd_def:
                cmd_def.deleteMe()
                
        handlers.clear()
    except Exception:
        pass

if __name__ == '__main__':
    # Allows running as a standalone script
    try:
        run(None)
    except Exception:
        pass
