import os
import requests
import time
from zipfile import ZipFile


# Códigos ANSI para colores
COLOR_GREEN = "\033[92m"
COLOR_BLUE = "\033[94m"
COLOR_RED = "\033[91m"
COLOR_ORANGE = "\033[38;5;208m"
COLOR_RESET = "\033[0m"


#======================================= SÓLO CAMBIAR ESTO ==================

dir_images = 'images/' # Directorio de las imágenes
dir_temp = 'temp/' # Directorio temporal

token_file_path = 'token_OSC'
    
#=======================================  No need to change anything below ==================

size_to_split = 200000000 # 200MB es el tamaño máximo de cada parte (el archivo zip total puede ser de hasta 2GB)
limit_filesize = 0
limit_photos = 0
credit = 0
allowed_extensions = ['.jpg', '.jpeg', '.JPG', '.JPEG', '.png', '.PNG'] # Extensiones de archivo permitidas
user = 'openscan'
pw = 'free'
server = 'http://openscanfeedback.dnsuser.de:1334/'
msg = {}

#---------------------------------------------------------------------

def stop(msg):
    
    """Detiene la ejecución del programa y muestra un mensaje."""
    
    print(f"{COLOR_RED}[ERROR] {msg}{COLOR_RESET}")
    while True:
        pass

#---------------------------------------------------------------------

def OpenScanCloud(cmd, msg):
    
    """Envía una solicitud al servidor de OpenScanCloud."""
    
    r = requests.get(server + cmd, auth=(user, pw), params=msg)
    return r

#---------------------------------------------------------------------

def uploadAndStart(filelist, ulinks):
    
    """Sube los archivos al servidor y comienza el procesamiento."""
    
    print(f"{COLOR_GREEN}[STEP] Iniciando la subida de archivos...{COLOR_RESET}")
    i = 0
    for file in filelist:
        print(f"{COLOR_BLUE}[INFO] Subiendo parte {i+1} de {len(filelist)}: {file}{COLOR_RESET}")
        link = ulinks[i]
        i += 1

        data = open(file, 'rb').read()
        r = requests.post(url=link, data=data, headers={'Content-type': 'application/octet-stream'})
        if r.status_code != 200:
            stop('No se pudo subir el archivo')

    print(f"{COLOR_GREEN}[STEP] Iniciando el proyecto...{COLOR_RESET}")
    r = OpenScanCloud('startProject', msg)
    if r.status_code != 200:
        stop('No se pudo iniciar el procesamiento')
    print(f"{COLOR_GREEN}[STEP] Procesamiento iniciado. Recibirás un correo pronto.{COLOR_RESET}")

#---------------------------------------------------------------------

def getAndVerifyToken():
    
    """Verifica el token y obtiene los límites de uso."""
    
    print(f"{COLOR_GREEN}[STEP] Verificando token...{COLOR_RESET}")
    global limit_filesize
    global limit_photos
    global credit

    if not os.path.exists(token_file_path):
        stop(f"El archivo '{token_file_path}' no existe. Crea el archivo y guarda tu token en él.")

    with open(token_file_path, 'r') as file:
        token = file.read().strip()
        if not token:
            stop(f"El archivo '{token_file_path}' está vacío. Agrega tu token.")

    msg['token'] = token

    tokenInfo = OpenScanCloud('getTokenInfo', msg)
    if tokenInfo.status_code != 200:
        stop('Token inválido')

    limit_filesize = tokenInfo.json()['limit_filesize']
    limit_photos = tokenInfo.json()['limit_photos']
    credit = tokenInfo.json()['credit']

    print(f"{COLOR_BLUE}[INFO] Límite de tamaño de archivo: {limit_filesize / 1e6} MB{COLOR_RESET}")
    print(f"{COLOR_BLUE}[INFO] Límite de fotos: {limit_photos}{COLOR_RESET}")
    print(f"{COLOR_BLUE}[INFO] Créditos disponibles: {credit}{COLOR_RESET}")

#---------------------------------------------------------------------

def select_folders(base_dir):
    
    """Permite al usuario seleccionar carpetas dentro del directorio base."""
    
    print(f"{COLOR_GREEN}[STEP] Seleccionando carpetas...{COLOR_RESET}")
    folders = [f for f in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, f))]
    
    if not folders:
        print(f"{COLOR_RED}[ERROR] No se encontraron carpetas en {base_dir}{COLOR_RESET}")
        return []

    print(f"{COLOR_BLUE}[INFO] Carpetas disponibles:{COLOR_RESET}")
    for i, folder in enumerate(folders):
        print(f"{i + 1}. {folder}")

    selected = input(f"{COLOR_ORANGE}[INPUT] Ingresa los números de las carpetas que deseas procesar (separados por comas): {COLOR_RESET}")
    selected_indices = [int(i.strip()) - 1 for i in selected.split(",") if i.strip().isdigit() and 0 <= int(i.strip()) - 1 < len(folders)]
    
    if not selected_indices:
        print(f"{COLOR_RED}[ERROR] No se seleccionaron carpetas válidas.{COLOR_RESET}")
        return []

    selected_folders = [folders[idx] for idx in selected_indices]
    print(f"{COLOR_BLUE}[INFO] Carpetas seleccionadas:{COLOR_RESET}")
    for folder in selected_folders:
        print(f"- {folder}")

    confirm = input(f"{COLOR_ORANGE}[INPUT] ¿Procesar las carpetas seleccionadas? (S/n): {COLOR_RESET}").strip().lower()
    if confirm == 'n':
        print(f"{COLOR_BLUE}[INFO] Procesamiento cancelado.{COLOR_RESET}")
        return []
    
    return selected_folders

#---------------------------------------------------------------------

def prepareSet():
    
    """Prepara el conjunto de imágenes para ser procesadas."""
    
    print(f"{COLOR_GREEN}[STEP] Preparando el conjunto de imágenes...{COLOR_RESET}")
    selected_folders = select_folders(dir_images)
    if not selected_folders:
        return []

    imagelist = []
    for folder in selected_folders:
        folder_path = os.path.join(dir_images, folder)
        for i in os.listdir(folder_path):
            if os.path.splitext(i)[1] in allowed_extensions:
                imagelist.append(os.path.join(folder, i))  # Guarda la ruta relativa

    if len(imagelist) == 0:
        print(f"{COLOR_RED}[ERROR] No se encontraron imágenes en las carpetas seleccionadas.{COLOR_RESET}")
        return []

    filesize = 0
    for i in imagelist:
        filesize += os.path.getsize(os.path.join(dir_images, i))

    msg['photos'] = len(imagelist)

    if filesize > limit_filesize or len(imagelist) > limit_photos:
        print(f"{COLOR_RED}[ERROR] Límites excedidos.{COLOR_RESET}")
        return []
    
    print(f"{COLOR_BLUE}[INFO] Total de imágenes: {len(imagelist)}{COLOR_RESET}")
    print(f"{COLOR_BLUE}[INFO] Tamaño total del conjunto: {filesize / 1e6} MB{COLOR_RESET}")
    return imagelist

#---------------------------------------------------------------------

def zipAndSplit(imagelist):
    
    """Comprime las imágenes y las divide en partes si es necesario."""
    
    print(f"{COLOR_GREEN}[STEP] Comprimiendo imágenes...{COLOR_RESET}")       
    for i in os.listdir(dir_temp):
        if i != ".gitkeep":
            os.remove(os.path.join(dir_temp, i))


    projectname = str(int(time.time()*100)) + '-OSC.zip'
    file = os.path.join(dir_temp, projectname)

    print(f"{COLOR_BLUE}[INFO] Nombre del proyecto: {projectname}{COLOR_RESET}")
    msg['project'] = projectname
    with ZipFile(file, 'w') as zip:
        for i in imagelist:
            zip.write(os.path.join(dir_images, i), i)

    msg['filesize'] = os.path.getsize(file)

    msg['partslist'] = [file]

    if os.path.getsize(file) > size_to_split:
        msg['partslist'] = []
        number = 1
        with open(file, 'rb') as f:
            chunk = f.read(size_to_split)
            while chunk:
                chunk_filename = file + '_' + str(number)
                with open(chunk_filename, 'wb+') as chunk_file:
                    chunk_file.write(chunk)
                msg['partslist'].append(chunk_filename)
                number += 1
                chunk = f.read(size_to_split)
        os.remove(file)
    
    msg['parts'] = len(msg['partslist'])
    print(f"{COLOR_BLUE}[INFO] Partes creadas: {msg['parts']}{COLOR_RESET}")
    
    print(f"{COLOR_GREEN}[STEP] Preparando proyecto en el servidor de OpenScanCloud...{COLOR_RESET}")
    r = OpenScanCloud('createProject', msg)
    if r.status_code != 200:
        stop('No se pudo crear el proyecto')
    msg['ulink'] = r.json()['ulink']



#============================================= Ejecución principal

getAndVerifyToken()

while True:
    imagelist = prepareSet()
    if imagelist:
        zipAndSplit(imagelist)
        uploadAndStart(msg['partslist'], msg['ulink'])
    
    continuar = input(f"{COLOR_ORANGE}[INPUT] ¿Deseas procesar otra carpeta? (S/n): {COLOR_RESET}").strip().lower()
    if continuar == 'n':
        print(f"{COLOR_GREEN}[INFO] Proceso finalizado.{COLOR_RESET}")
        break