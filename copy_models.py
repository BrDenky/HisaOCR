import os
import shutil

def main():
    src = os.path.expanduser(r"~/.paddlex/official_models")
    dest = os.path.abspath("models")
    
    if not os.path.exists(src):
        print(f"Error: La carpeta de origen {src} no existe.")
        return
        
    os.makedirs(dest, exist_ok=True)
    print(f"Copiando modelos desde {src} hacia {dest}...")
    
    for item in os.listdir(src):
        s_item = os.path.join(src, item)
        d_item = os.path.join(dest, item)
        
        if os.path.isdir(s_item):
            if os.path.exists(d_item):
                print(f"El modelo '{item}' ya existe en destino. Omitiendo.")
            else:
                print(f"Copiando '{item}'...")
                try:
                    shutil.copytree(s_item, d_item)
                    print(f"'{item}' copiado.")
                except Exception as e:
                    print(f"Error al copiar '{item}': {e}")
                
    print("¡Copiado completado con éxito!")

if __name__ == "__main__":
    main()
