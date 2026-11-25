import os
import re
import json
import urllib.request
from datetime import datetime
from bs4 import BeautifulSoup

# 1. Monitores rastreados nas lojas
PRODUTOS = [
    {
        "id": "asus_vg34",
        "nome": "ASUS TUF VG34WQML5A (34\" 180Hz)",
        "termo_filtro": "VG34WQML5A",
        "url_direta": "https://www.buscape.com.br/monitor/monitor-gamer-va-34-antirreflexo-asus-wqhd-vg34wqml5a",
        "url_busca": "https://www.buscape.com.br/search?q=VG34WQML5A"
    },
    {
        "id": "lg_34g600a",
        "nome": "LG UltraGear Curvo 34G600A (34\" 160Hz)",
        "termo_filtro": "34G600A",
        "url_direta": None,
        "url_busca": "https://www.buscape.com.br/search?q=34G600A"
    }
]

# 2. Termos que disparam o radar de cupons do Pelando
TERMOS_RADAR_PELANDO = ["VG34WQML5A", "VG34", "34G600A"]

HISTORICO_FILE = "historico.json"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

def enviar_telegram(mensagem):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram Token ou Chat ID nao configurados.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensagem,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            print("Telegram enviado com sucesso!")
    except Exception as e:
        print("Erro ao enviar Telegram:", e)

def extrair_cupom_ou_beneficio(texto):
    """Detecta menções a cupons, descontos no carrinho ou cashback"""
    beneficios = []
    # Procura menção a cupom
    cupom_match = re.search(r"(cupom[:\s]+[A-Z0-9_-]+|\bcom cupom\b|\bcupom de R\$\s*[\d\.,]+)", texto, re.IGNORECASE)
    if cupom_match:
        beneficios.append(cupom_match.group(0).strip())
    # Procura cashback
    cashback_match = re.search(r"(\d+%\s+de\s+volta|\bSuper Cashback\b)", texto, re.IGNORECASE)
    if cashback_match:
        beneficios.append(cashback_match.group(0).strip())
        
    return " | ".join(beneficios) if beneficios else "Sem cupom aparente"

def extrair_melhor_oferta(produto):
    ofertas = []
    
    # 1. Página direta do produto (quando disponível)
    if produto.get("url_direta"):
        try:
            req = urllib.request.Request(produto["url_direta"], headers=HEADERS)
            with urllib.request.urlopen(req, timeout=12) as r:
                html = r.read().decode("utf-8", errors="ignore")
                soup = BeautifulSoup(html, "html.parser")
                for card in soup.select("[data-testid*='offer-card'], [data-testid*='lead-merchant']"):
                    txt = card.get_text(" ")
                    num_match = re.search(r"R\$\s*([\d\.]+),(\d{2})", txt)
                    if not num_match: continue
                    inteiro = num_match.group(1).replace(".", "")
                    preco = float(f"{inteiro}.{num_match.group(2)}")
                    
                    parc_match = re.search(r"(\d{1,2}x\s+de\s+R\$\s*[\d\.,]+)", txt, re.IGNORECASE)
                    parc = parc_match.group(1) if parc_match else "Consulte condições"
                    
                    cupom_info = extrair_cupom_ou_beneficio(txt)

                    loja = "Loja Parceira"
                    for cand in ["KaBuM!", "Magazine Luiza", "Amazon", "Pichau", "Terabyte", "Mercado Livre", "Girafa", "Fast Shop", "Webcontinental", "Loja Online LG"]:
                        if cand.lower() in txt.lower(): loja = cand; break
                        
                    link_tag = card.select_one("a[href]")
                    href_val = link_tag.get("href") if link_tag else ""
                    link = f"https://www.buscape.com.br{href_val}" if href_val.startswith("/") else produto["url_direta"]
                    ofertas.append({"loja": loja, "preco": preco, "parcelamento": parc, "cupom": cupom_info, "link": link})
        except Exception as e:
            print(f"Aviso busca direta {produto['id']}:", e)

    # 2. Busca geral
    if not ofertas:
        try:
            req = urllib.request.Request(produto["url_busca"], headers=HEADERS)
            with urllib.request.urlopen(req, timeout=12) as r:
                html = r.read().decode("utf-8", errors="ignore")
                soup = BeautifulSoup(html, "html.parser")
                for card in soup.select("a[data-testid*='product-card']"):
                    txt = card.get_text(" ")
                    if produto["termo_filtro"].lower() in txt.lower() and "suporte" not in txt.lower() and "braço" not in txt.lower():
                        num_match = re.search(r"R\$\s*([\d\.]+),(\d{2})", txt)
                        if not num_match: continue
                        inteiro = num_match.group(1).replace(".", "")
                        preco = float(f"{inteiro}.{num_match.group(2)}")
                        
                        parc_match = re.search(r"(\d{1,2}x\s+de\s+R\$\s*[\d\.,]+)", txt, re.IGNORECASE)
                        parc = parc_match.group(1) if parc_match else "Consulte condições"
                        cupom_info = extrair_cupom_ou_beneficio(txt)
                        
                        loja = "Loja Parceira"
                        for cand in ["KaBuM!", "Magazine Luiza", "Amazon", "Pichau", "Terabyte", "Mercado Livre", "Girafa", "Fast Shop", "Webcontinental", "Loja Online LG"]:
                            if cand.lower() in txt.lower(): loja = cand; break
                            
                        href = card.get("href") or ""
                        link = f"https://www.buscape.com.br{href}" if href.startswith("/") else produto["url_busca"]
                        ofertas.append({"loja": loja, "preco": preco, "parcelamento": parc, "cupom": cupom_info, "link": link})
        except Exception as e:
            print(f"Erro busca geral {produto['id']}:", e)

    if ofertas:
        ofertas.sort(key=lambda x: x["preco"])
        return ofertas[0]
    return None

def checar_radar_pelando(historico_links):
    """Varre as últimas promoções do Pelando procurando por cupons dos monitores"""
    novas_ofertas = []
    url = "https://www.pelando.com.br/recentes"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode("utf-8", errors="ignore")
            soup = BeautifulSoup(html, "html.parser")
            for a_tag in soup.select("a[href*='/d/']"):
                titulo = a_tag.get_text(" ").strip()
                href = a_tag.get("href", "")
                if not titulo or not href: continue
                
                full_link = href if href.startswith("http") else f"https://www.pelando.com.br{href}"
                
                # Se já alertamos sobre esse link antes, pula
                if full_link in historico_links:
                    continue

                for termo in TERMOS_RADAR_PELANDO:
                    if termo.lower() in titulo.lower() and "suporte" not in titulo.lower():
                        novas_ofertas.append({"titulo": titulo, "link": full_link})
                        historico_links.append(full_link)
                        break
    except Exception as e:
        print("Aviso ao consultar Pelando:", e)
        
    return novas_ofertas

def main():
    historico_geral = {}
    if os.path.exists(HISTORICO_FILE):
        try:
            with open(HISTORICO_FILE, "r", encoding="utf-8") as f:
                historico_geral = json.load(f)
        except Exception:
            historico_geral = {}

    # Migra formato antigo se necessário
    if "menor_preco" in historico_geral and "asus_vg34" not in historico_geral:
        historico_geral = {"asus_vg34": historico_geral}

    historico_pelando = historico_geral.setdefault("pelando_links", [])

    # === ESTRATÉGIA 1: Lojas com Preço e Cupons Embutidos ===
    for prod in PRODUTOS:
        p_id = prod["id"]
        nome_prod = prod["nome"]
        
        melhor = extrair_melhor_oferta(prod)
        if not melhor:
            continue

        preco_atual = melhor["preco"]
        parc_atual = melhor["parcelamento"]
        loja_atual = melhor["loja"]
        cupom_atual = melhor["cupom"]
        link_atual = melhor["link"]

        hist_prod = historico_geral.get(p_id, {})
        menor_gravado = hist_prod.get("menor_preco")

        # Primeiro registro do produto
        if menor_gravado is None:
            historico_geral[p_id] = {
                "menor_preco": preco_atual,
                "parcelamento": parc_atual,
                "loja": loja_atual,
                "data": datetime.now().strftime("%d/%m/%Y %H:%M")
            }
            msg = (
                f"🤖 *Novo Produto Sendo Monitorado 24h!*\n\n"
                f"📦 *{nome_prod}*\n\n"
                f"💵 *À vista:* R$ {preco_atual:,.2f}\n"
                f"💳 *Parcelado:* {parc_atual}\n"
                f"🏪 *Loja:* {loja_atual}\n"
                f"🎟️ *Condição/Cupom:* {cupom_atual}\n\n"
                f"🔗 [Acessar Oferta Direta]({link_atual})\n\n"
                f"🔔 _Avisarei assim que este monitor tiver qualquer queda de preço ou cupom!_"
            )
            enviar_telegram(msg)
            continue

        # Alerta se o preço cair
        if preco_atual < menor_gravado:
            economia = menor_gravado - preco_atual
            msg = (
                f"🚨 *QUEDA DE PREÇO DETECTADA!* 🚨\n\n"
                f"📦 *{nome_prod}*\n\n"
                f"❌ *Antes:* R$ {menor_gravado:,.2f}\n"
                f"💵 *Novo valor à vista:* R$ {preco_atual:,.2f}\n"
                f"💳 *Parcelado:* {parc_atual}\n"
                f"📉 *Economia de:* R$ {economia:,.2f}\n"
                f"🏪 *Loja:* {loja_atual}\n"
                f"🎟️ *Condição/Cupom:* {cupom_atual}\n\n"
                f"🔗 [IR DIRETO PARA A OFERTA]({link_atual})"
            )
            enviar_telegram(msg)

            historico_geral[p_id] = {
                "menor_preco": preco_atual,
                "parcelamento": parc_atual,
                "loja": loja_atual,
                "data": datetime.now().strftime("%d/%m/%Y %H:%M")
            }

    # === ESTRATÉGIA 2: Radar da Comunidade (Pelando) ===
    achados_pelando = checar_radar_pelando(historico_pelando)
    for achado in achados_pelando:
        msg_pelando = (
            f"🎟️🔥 *PROMOÇÃO COM CUPOM DETECTADA NO PELANDO!* 🔥🎟️\n\n"
            f"A comunidade acabou de postar uma oferta para o seu monitor:\n\n"
            f"📢 *{achado['titulo']}*\n\n"
            f"🔗 [ABRIR PROMOÇÃO E VER O CUPOM]({achado['link']})\n\n"
            f"⚡ _Corra antes que o cupom esgote!_"
        )
        enviar_telegram(msg_pelando)

    # Limita histórico do Pelando para não crescer infinitamente
    historico_geral["pelando_links"] = historico_pelando[-50:]

    with open(HISTORICO_FILE, "w", encoding="utf-8") as f:
        json.dump(historico_geral, f, indent=2)

if __name__ == "__main__":
    main()
