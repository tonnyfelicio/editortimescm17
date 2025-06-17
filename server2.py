from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
import os
from werkzeug.utils import secure_filename
import uuid
import time

app = Flask(__name__)
app.secret_key = 'secret'

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

OFFSET_INICIAL = 0x1FFC45E
OFFSET_FINAL = 0x204C09E
TAMANHO_BLOCO = 320
OFFSET_NOME = 48
TAMANHO_NOME = 32
OFFSET_NOME_COMPLETO = 0
TAMANHO_NOME_COMPLETO = 48
OFFSET_ESTADIO = 80
TAMANHO_ESTADIO = 32
OFFSET_TECNICO = 112
TAMANHO_TECNICO = 32

# Helpers para carregar listas

def carregar_lista(caminho, separador):
    lista = {}
    with open(caminho, encoding="utf-8") as f:
        for linha in f:
            if separador in linha:
                nome, codigo = linha.strip().split(separador, 1)
                lista[nome.strip()] = codigo.strip()
    return lista

def carregar_uniformes():
    return carregar_lista("dados/uniforme.txt", "/")

def carregar_dinheiro():
    lista = {}
    with open("dados/dinheiro.txt", encoding="utf-8") as f:
        for linha in f:
            if ">" in linha:
                nome, codigo = linha.strip().split(">", 1)
                codigo_sem_espacos = codigo.strip().replace(" ", "").upper()
                lista[nome.strip()] = codigo_sem_espacos
    return lista

def carregar_paises():
    return carregar_lista("dados/paises.txt", "/")

def carregar_taticas(nome):
    return carregar_lista(f"dados/{nome}.txt", "/")

def formatar_le_hex(valor):
    return f"{valor & 0xFF:02X}{(valor >> 8) & 0xFF:02X}"

def carregar_times(arquivo_bin):
    times = []
    with open(arquivo_bin, "rb") as f:
        offset = OFFSET_INICIAL
        while offset + TAMANHO_BLOCO <= OFFSET_FINAL:
            f.seek(offset + OFFSET_NOME)
            nome = f.read(TAMANHO_NOME).split(b'\x00')[0].decode("utf-8", errors="ignore").strip()
            times.append({"id": formatar_le_hex(len(times)+1), "nome": nome, "offset": offset})
            offset += TAMANHO_BLOCO
    return times

def rgb_para_hex(bgr):
    b, g, r = bgr
    return f"#{r:02X}{g:02X}{b:02X}"

def hex_para_rgb(hex_str):
    r = int(hex_str[1:3], 16)
    g = int(hex_str[3:5], 16)
    b = int(hex_str[5:7], 16)
    return b, g, r

def ler_dados(offset, arquivo_bin):
    with open(arquivo_bin, "rb") as f:
        f.seek(offset + OFFSET_NOME)
        nome = f.read(TAMANHO_NOME).split(b'\x00')[0].decode("utf-8", errors="ignore").strip()
        f.seek(offset + OFFSET_NOME_COMPLETO)
        nome_completo = f.read(TAMANHO_NOME_COMPLETO).split(b'\x00')[0].decode("utf-8", errors="ignore").strip()
        f.seek(offset + OFFSET_ESTADIO)
        estadio = f.read(TAMANHO_ESTADIO).split(b'\x00')[0].decode("utf-8", errors="ignore").strip()
        f.seek(offset + OFFSET_TECNICO)
        tecnico = f.read(TAMANHO_TECNICO).split(b'\x00')[0].decode("utf-8", errors="ignore").strip()

        f.seek(offset + 244)
        cor1 = rgb_para_hex(f.read(3))
        f.seek(offset + 248)
        b2 = f.read(1)[0]
        g2 = f.read(1)[0]
        r2 = f.read(1)[0]
        cor2 = f"#{r2:02X}{g2:02X}{b2:02X}"
        f.seek(offset + 252)
        cor1_fora = rgb_para_hex(f.read(3))
        f.seek(offset + 256)
        cor2_fora = rgb_para_hex(f.read(3))

        f.seek(offset + 269)
        uniforme_bytes = f.read(2).hex().upper()

        f.seek(offset + 305)
        dinheiro = f.read(4).hex().upper()

        f.seek(offset + 272)
        tatica = f.read(1).hex().upper()
        pais = f.read(1).hex().upper()

    return {
        "nome": nome,
        "nome_completo": nome_completo,
        "estadio": estadio,
        "tecnico": tecnico,
        "cor1": cor1,
        "cor2": cor2,
        "cor1_fora": cor1_fora,
        "cor2_fora": cor2_fora,
        "uniforme": uniforme_bytes,
        "dinheiro": dinheiro,
        "tatica": tatica,
        "pais": pais
    }

def limpar_uploads_antigos(pasta="uploads", limite_segundos=3600):
    agora = time.time()
    for nome in os.listdir(pasta):
        caminho = os.path.join(pasta, nome)
        if os.path.isfile(caminho):
            modificado = os.path.getmtime(caminho)
            if agora - modificado > limite_segundos:
                try:
                    os.remove(caminho)
                except Exception as e:
                    print(f"Erro ao deletar {caminho}: {e}")

@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        # Limpa arquivos antigos antes de salvar um novo
        limpar_uploads_antigos(app.config["UPLOAD_FOLDER"])

        arquivo = request.files.get("arquivo")
        if arquivo and arquivo.filename:
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])

            nome_seguro = secure_filename(arquivo.filename)
            extensao = os.path.splitext(nome_seguro)[1]
            nome_unico = f"{uuid.uuid4().hex}{extensao}"
            caminho = os.path.abspath(os.path.join(app.config["UPLOAD_FOLDER"], nome_unico))
            arquivo.save(caminho)

            session['arquivo_carregado'] = caminho

            flash(f"Arquivo carregado: {nome_unico}")
            return redirect(url_for("index"))
        else:
            flash("Nenhum arquivo selecionado.")
    return render_template("upload.html")

@app.route("/")
def index():
    arquivo_caminho = session.get('arquivo_carregado')
    if not arquivo_caminho or not os.path.isfile(arquivo_caminho):
        flash("Nenhum arquivo carregado ou arquivo não encontrado. Por favor, faça upload.")
        return redirect(url_for("upload"))

    termo = request.args.get("busca", "").strip().lower()
    todos_times = carregar_times(arquivo_caminho)
    if termo:
        times = [time for time in todos_times if termo in time["nome"].lower()]
    else:
        times = todos_times
    return render_template("index.html", times=times, busca=termo)

@app.route("/baixar")
def baixar():
    arquivo_caminho = session.get('arquivo_carregado')
    if not arquivo_caminho or not os.path.isfile(arquivo_caminho):
        flash("Nenhum arquivo carregado ou arquivo não encontrado.")
        return redirect(url_for("upload"))
    return send_file(arquivo_caminho, as_attachment=True)

@app.route("/editar/<hex_id>")
def editar(hex_id):
    arquivo_caminho = session.get('arquivo_carregado')
    if not arquivo_caminho or not os.path.isfile(arquivo_caminho):
        flash("Nenhum arquivo carregado ou arquivo não encontrado.")
        return redirect(url_for("upload"))

    byte1 = int(hex_id[0:2], 16)
    byte2 = int(hex_id[2:4], 16)
    index = (byte2 << 8) + byte1 - 1
    times = carregar_times(arquivo_caminho)
    if 0 <= index < len(times):
        offset = times[index]['offset']
        dados = ler_dados(offset, arquivo_caminho)

        paises = carregar_paises()
        taticasA = carregar_taticas("taticasA")
        taticasB = carregar_taticas("taticasB")
        todas_taticas = {
            "A": list(taticasA.keys()),
            "B": list(taticasB.keys()),
            "Todas": list(set(taticasA.keys()) | set(taticasB.keys()))
        }

        tatica_byte = int(dados["tatica"], 16)
        pais_byte = dados["pais"]

        # Definir byte1 do país conforme a lógica
        if tatica_byte < 0x81:
            byte1_pais = "01"
        else:
            byte1_pais = "81"

        # Formar código completo do país para comparar com paises.txt
        codigo_pais = f"{byte1_pais} {pais_byte}".upper()

        # Inverter dicionário de países para achar nome
        paises_inv = {v.upper(): k for k, v in paises.items()}
        dados["pais"] = paises_inv.get(codigo_pais, "??")

        # Identificar de qual lista a tática pertence
        taticasA_inv = {v.upper(): k for k, v in taticasA.items()}
        taticasB_inv = {v.upper(): k for k, v in taticasB.items()}

        dados["tatica"] = taticasA_inv.get(dados["tatica"], taticasB_inv.get(dados["tatica"], "??"))

        uniformes = carregar_uniformes()
        dados['uniforme'] = next((k for k, v in uniformes.items() if v.replace(" ", "").upper() == dados['uniforme']), '')

        dinheiros = carregar_dinheiro()

        with open(arquivo_caminho, "rb") as f:
            f.seek(offset + 305)
            dinheiro_bytes = f.read(4)
            dinheiro_hex = dinheiro_bytes.hex().upper()

        dinheiro_nome = next((nome for nome, valor in dinheiros.items() if valor == dinheiro_hex), "")
        dados["dinheiro"] = dinheiro_nome

        return render_template("editar.html", hex_id=hex_id, dados=dados,
                               paises=paises, uniformes=uniformes,
                               dinheiro_opcoes=dinheiros.keys(),
                               taticas_disponiveis=todas_taticas['Todas'],
                               todas_taticas=todas_taticas)
    else:
        flash("ID inválido")
        return redirect(url_for("index"))

@app.route("/salvar/<hex_id>", methods=["POST"])
def salvar(hex_id):
    arquivo_caminho = session.get('arquivo_carregado')
    if not arquivo_caminho or not os.path.isfile(arquivo_caminho):
        flash("Nenhum arquivo carregado ou arquivo não encontrado.")
        return redirect(url_for("upload"))

    byte1 = int(hex_id[0:2], 16)
    byte2 = int(hex_id[2:4], 16)
    index = (byte2 << 8) + byte1 - 1
    times = carregar_times(arquivo_caminho)
    if 0 <= index < len(times):
        offset = times[index]['offset']

        paises = carregar_paises()
        taticasA = carregar_taticas("taticasA")
        taticasB = carregar_taticas("taticasB")
        uniformes = carregar_uniformes()
        dinheiros = carregar_dinheiro()

        nome = request.form.get("nome", "").strip()
        nome_completo = request.form.get("nome_completo", "").strip()
        estadio = request.form.get("estadio", "").strip()
        tecnico = request.form.get("tecnico", "").strip()

        cor1 = request.form.get("cor1")
        cor2 = request.form.get("cor2")
        cor1_fora = request.form.get("cor1_fora")
        cor2_fora = request.form.get("cor2_fora")

        uniforme_nome = request.form.get("uniforme")
        uniforme = uniformes.get(uniforme_nome)

        dinheiro_nome = request.form.get("dinheiro")
        dinheiro = dinheiros.get(dinheiro_nome)

        pais_nome = request.form.get("pais")
        tatica_nome = request.form.get("tatica")
        pais_cod = paises.get(pais_nome)

        byte1_pais = "00"
        byte2_pais = "00"
        tatica = None

        if pais_cod:
            pais_parts = pais_cod.split()
            if len(pais_parts) >= 2:
                byte1_pais = pais_parts[0]
                byte2_pais = pais_parts[1]

                # Seleção da tática conforme byte1 do país
                if byte1_pais.upper() == "01":
                    tatica = taticasA.get(tatica_nome)
                elif byte1_pais.upper() == "81":
                    tatica = taticasB.get(tatica_nome)
                else:
                    # Caso byte1 diferente, tenta nas duas listas
                    tatica = taticasA.get(tatica_nome) or taticasB.get(tatica_nome)

        with open(arquivo_caminho, "r+b") as f:
            f.seek(offset + OFFSET_NOME)
            f.write(nome.encode("utf-8")[:TAMANHO_NOME].ljust(TAMANHO_NOME, b'\x00'))
            f.seek(offset + OFFSET_NOME_COMPLETO)
            f.write(nome_completo.encode("utf-8")[:TAMANHO_NOME_COMPLETO].ljust(TAMANHO_NOME_COMPLETO, b'\x00'))
            f.seek(offset + OFFSET_ESTADIO)
            f.write(estadio.encode("utf-8")[:TAMANHO_ESTADIO].ljust(TAMANHO_ESTADIO, b'\x00'))
            f.seek(offset + OFFSET_TECNICO)
            f.write(tecnico.encode("utf-8")[:TAMANHO_TECNICO].ljust(TAMANHO_TECNICO, b'\x00'))

            f.seek(offset + 244)
            f.write(bytes(hex_para_rgb(cor1)))
            f.seek(offset + 248)
            f.write(bytes(hex_para_rgb(cor2)))
            f.seek(offset + 252)
            f.write(bytes(hex_para_rgb(cor1_fora)))
            f.seek(offset + 256)
            f.write(bytes(hex_para_rgb(cor2_fora)))

            if uniforme:
                f.seek(offset + 269)
                f.write(bytes.fromhex(uniforme.replace(" ", "")))

            if dinheiro:
                f.seek(offset + 305)
                f.write(bytes.fromhex(dinheiro))

            if tatica and byte2_pais != "00":
                f.seek(offset + 272)
                f.write(bytes.fromhex(tatica))
                f.write(bytes.fromhex(byte2_pais))

        flash("Alterações salvas com sucesso!")
    else:
        flash("ID inválido")
    return redirect(url_for("index"))

if __name__ == '__main__':
    app.run(debug=True)
