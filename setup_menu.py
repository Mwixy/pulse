import os
import sys
import subprocess
import msvcrt
import re
from pathlib import Path

def get_installer_version():
    setup_path = Path("setup.py")
    if not setup_path.exists():
        return "0.0.0"
    content = setup_path.read_text(encoding="utf-8")
    match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
    if match:
        return match.group(1)
    return "0.0.0"

def get_installed_version():
    try:
        if sys.version_info >= (3, 8):
            from importlib.metadata import version, PackageNotFoundError
            try:
                return version("pulse")
            except PackageNotFoundError:
                return None
    except Exception:
        pass
    
    # Fallback to pip
    result = subprocess.run([sys.executable, "-m", "pip", "show", "pulse"], capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if line.startswith("Version:"):
            return line.split(":")[1].strip()
    return None

def parse_version(v):
    return tuple(map(int, v.split('.')))

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def render_menu(title, options, selected_idx):
    clear_screen()
    print("====================================")
    print("     Pulse Installation Setup")
    print("====================================\n")
    print(title + "\n")
    for i, opt in enumerate(options):
        if i == selected_idx:
            print(f"  > {opt}")
        else:
            print(f"    {opt}")
    print("\n(Use UP/DOWN arrows and press ENTER to select)")

def select_from_menu(title, options):
    selected_idx = 0
    while True:
        render_menu(title, options, selected_idx)
        key = msvcrt.getch()
        if key in (b'\xe0', b'\x00'): # Special keys
            arrow = msvcrt.getch()
            if arrow == b'H': # Up
                selected_idx = max(0, selected_idx - 1)
            elif arrow == b'P': # Down
                selected_idx = min(len(options) - 1, selected_idx + 1)
        elif key == b'\r': # Enter
            return options[selected_idx]

def run_install():
    print("\nInstalling Pulse...")
    res = subprocess.run([sys.executable, "-m", "pip", "install", "-e", "."])
    if res.returncode == 0:
        print("\nRegistering .pulse file association...")
        python_exe = sys.executable
        
        # 1. User-level registry (Does NOT require Admin, guarantees it works)
        subprocess.run(["reg", "add", r"HKCU\Software\Classes\.pulse", "/ve", "/d", "PulseScript", "/f"], capture_output=True)
        subprocess.run(["reg", "add", r"HKCU\Software\Classes\PulseScript\shell\open\command", "/ve", "/d", f'"{python_exe}" -m pulse "%1" %*', "/f"], capture_output=True)
        
        # 2. System-level global (Requires Admin)
        os.system('assoc .pulse=PulseScript >nul 2>&1')
        os.system(f'ftype PulseScript="{python_exe}" -m pulse "%1" %* >nul 2>&1')
        # 3. Add Custom Icon!
        try:
            import PIL
        except ImportError:
            print("Downloading image processor for custom icons...")
            subprocess.run([sys.executable, "-m", "pip", "install", "pillow"], capture_output=True)
            
        try:
            from PIL import Image
            icon_path = Path("logo.ico").absolute()
            if Path("examples/logo.png").exists():
                img = Image.open("examples/logo.png")
                img.save(icon_path, format="ICO", sizes=[(256, 256)])
                subprocess.run(["reg", "add", r"HKCU\Software\Classes\PulseScript\DefaultIcon", "/ve", "/d", str(icon_path), "/f"], capture_output=True)
                
                import ctypes
                # SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, None, None)
                ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
        except Exception as e:
            print("Could not set custom icon:", e)

        print("\n========================================================")
        print("SUCCESS: Pulse has been successfully installed!")
        print("========================================================")
    else:
        print("\n[X] ERROR: Installation failed.")

def run_uninstall():
    print("\nUninstalling Pulse...")
    subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "pulse"])
    print("\nSUCCESS: Pulse has been uninstalled.")

def main():
    installer_ver = get_installer_version()
    installed_ver = get_installed_version()

    if installed_ver is None:
        title = f"Ready to install Pulse version {installer_ver}."
        options = ["Install", "Exit"]
    else:
        inst_v = parse_version(installed_ver)
        pack_v = parse_version(installer_ver)

        if inst_v == pack_v:
            title = f"Pulse {installed_ver} is already installed."
            options = ["Reinstall", "Uninstall"]
        elif inst_v < pack_v:
            title = f"Update available: {installed_ver} -> {installer_ver}"
            options = ["Update", "Uninstall"]
        else:
            title = f"A newer version of Pulse is already installed!\nAre you sure you want to downgrade from {installed_ver} to {installer_ver}?"
            options = ["Downgrade", "Uninstall"]
            
    options.append("Cancel Setup")
    
    choice = select_from_menu(title, options)
    
    if choice in ("Install", "Reinstall", "Update", "Downgrade"):
        run_install()
    elif choice == "Uninstall":
        run_uninstall()
    else:
        print("\nSetup cancelled.")
        
    print()
    os.system('pause')

if __name__ == "__main__":
    main()
