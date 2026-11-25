import os
import re
import json
import urllib.request
from datetime import datetime
from bs4 import BeautifulSoup

MODELO = "VG34WQML5A"
URL_BUSCAPE_PRODUTO = "https://www.buscape.com.br/monitor/monitor-gamer-va-34-antirreflexo-asus-wqhd-vg34wqml5a"
URL_BUSCAPE_BUSCA = f"https://www.buscape.com.br/search?q={MODELO}"
HISTORICO_FILE = "historico.json"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

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

def extrair_ofertas():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    ofertas = []
    
    # Tenta primeiro a página do produto com todas as lojas
    req = urllib.request.Request(URL_BUSCAPE_PRODUTO, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="ignore")
            soup = BeautifulSoup(html, "html.parser")
            
            cards = soup.select("[data-testid*='offer-card'], [data-testid*='lead-merchant']")
            for card in cards:
                card_text = card.get_text(" ")
                num_match = re.search(r"R\$\s*([\d\.]+),(\d{2})", card_text)
                if not num_match:
                    continue
                inteiro = num_match.group(1).replace(".", "")
                centavos = num_match.group(2)
                preco = float(f"{inteiro}.{centavos}")
                
                # Identifica loja
                loja = "Loja parceira"
                for cand in ["KaBuM!", "Magazine Luiza", "Amazon", "Pichau", "Terabyte", "Mercado Livre", "Girafa", "Fast Shop", "Casas Bahia"]:
                    if cand.lower() in card_text.lower():
                        loja = cand
                        break
                        
                link_tag = card.select_one("a[href]")
                href_val = link_tag.get("href") if link_tag else ""
                link = f"https://www.buscape.com.br{href_val}" if href_val.startswith("/") else URL_BUSCAPE_PRODUTO
                ofertas.append({"loja": loja, "preco": preco, "link": link})
    except Exception as e:
        print("Aviso ao acessar pagina do produto:", e)

    # Se a lista direta falhar, usa a busca geral
    if not ofertas:
        req_b = urllib.request.Request(URL_BUSCAPE_BUSCA, headers=headers)
        try:
            with urllib.request.urlopen(req_b, timeout=15) as r:
                html = r.read().decode("utf-8", errors="ignore")
                soup = BeautifulSoup(html, "html.parser")
                for card in soup.select("a[data-testid*='product-card']"):
                    txt = card.get_text(" ")
                    if MODELO.lower() in txt.lower():
                        num_match = re.search(r"R\$\s*([\d\.]+),(\d{2})", txt)
                        if num_match:
                            val = float(f"{num_match.group(1).replace('.', '')}.{num_match.group(2)}")
                            href = card.get("href")
                            link = f"https://www.buscape.com.br{href}" if href.startswith("/") else URL_BUSCAPE_BUSCA
                            ofertas.append({"loja": "Melhor Oferta", "preco": val, "link": link})
        except Exception as e:
            print("Erro na busca de contingencia:", e)
            
    return ofertas

def main():
    ofertas = extrair_ofertas()
    if not ofertas:
        print("Nenhuma oferta encontrada nesta checagem.")
        return

    # Ordena para pegar a mais barata
    ofertas.sort(key=lambda x: x["preco"])
    melhor = ofertas[0]
    preco_atual = melhor["preco"]
    loja_atual = melhor["loja"]
    link_atual = melhor["link"]
    
    print(f"Menor preco encontrado: R$ {preco_atual:.2f} na {loja_atual}")

    # Leitura do histórico anterior
    historico = {}
    if os.path.exists(HISTORICO_FILE):
        try:
            with open(HISTORICO_FILE, "r", encoding="utf-8") as f:
                historico = json.load(f)
        except Exception:
            historico = {}

    menor_historico = historico.get("menor_preco")

    # Primeira execução: registra o baseline e envia boas-vindas com o preço atual
    if menor_historico is None:
        historico = {
            "menor_preco": preco_atual,
            "loja": loja_atual,
            "data": datetime.now().strftime("%d/%m/%Y %H:%M")
        }
        with open(HISTORICO_FILE, "w", encoding="utf-8") as f:
            json.dump(historico, f, indent=2)
            
        msg = (
            f"🤖 *Monitor Ativado com Sucesso!*\n\n"
            f"Estou monitorando 24h o monitor *ASUS TUF VG34WQML5A*.\n\n"
            f"📊 *Preço base atual:* R$ {preco_atual:,.2f}\n"
            f"🏪 *Loja:* {loja_atual}\n\n"
            f"🔗 [Ver Oferta Atual]({link_atual})\n\n"
            f"🔔 _Você receberá um novo alerta assim que o preço cair!_"
        )
        enviar_telegram(msg)
        return

    # Execuções seguintes: só alerta se o preço cair!
    if preco_atual < menor_historico:
        economia = menor_historico - preco_atual
        msg = (
            f"🚨 *QUEDA DE PREÇO DETECTADA!* 🚨\n\n"
            f"O monitor *ASUS TUF VG34WQML5A* baixou de valor!\n\n"
            f"❌ *Antes:* R$ {menor_historico:,.2f}\n"
            f"✅ *Agora:* R$ {preco_atual:,.2f}\n"
            f"📉 *Economia de:* R$ {economia:,.2f}\n"
            f"🏪 *Loja:* {loja_atual}\n\n"
            f"🔗 [IR DIRETO PARA A OFERTA]({link_atual})"
        )
        enviar_telegram(msg)

        # Atualiza histórico com o novo recorde
        historico["menor_preco"] = preco_atual
        historico["loja"] = loja_atual
        historico["data"] = datetime.now().strftime("%d/%m/%Y %H:%M")
        with open(HISTORICO_FILE, "w", encoding="utf-8") as f:
            json.dump(historico, f, indent=2)
    else:
        print(f"Preco estavel (Atual: R$ {preco_atual:.2f} | Menor registrado: R$ {menor_historico:.2f}). Nenhum alerta necessario.")

if __name__ == "__main__":
    main()
