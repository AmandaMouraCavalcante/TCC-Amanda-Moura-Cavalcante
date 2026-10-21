import os
import time
from datetime import datetime
import requests
from curl_cffi import requests as c_requests
import pandas as pd


def get_current_year():
    return datetime.now().year


def download_file(url, dest_path, timeout=60, use_impersonation=False, max_retries=3, force=False):
    """
    Baixa um arquivo da URL e salva localmente.
    Se o arquivo ja existir, nao baixa de novo para economizar tempo.
    """
    if not force and os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
        print(f"Arquivo {os.path.basename(dest_path)} ja existe. Pulando download.")
        return True

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    # Tenta baixar ate 3 vezes caso a conexao oscile
    for tentativa in range(1, max_retries + 1):
        try:
            if use_impersonation:
                # Usa curl_cffi simulando o Chrome para o portal da CCEE nao bloquear com erro 403
                response = c_requests.get(url, impersonate="chrome", stream=True, timeout=timeout)
            else:
                response = requests.get(url, headers=headers, stream=True, timeout=timeout)

            if response.status_code == 200:
                with open(dest_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=16384):
                        if chunk:
                            f.write(chunk)
                return True

            print(f"Tentativa {tentativa} falhou: status {response.status_code}")
        except Exception as e:
            print(f"Erro na tentativa {tentativa}: {e}")

        # Espera um pouco antes de tentar de novo
        if tentativa < max_retries:
            time.sleep(2 * tentativa)

    return False


def fetch_ccee_pld_via_api(dest_path, year=None, force=False):
    """
    Consulta a API de dados abertos da CCEE para pegar o link correto do PLD do ano informado.
    """
    if year is None:
        year = get_current_year()

    if not force and os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
        print(f"PLD {year} ja existe em cache local.")
        return True

    # Link da API CKAN do portal da CCEE
    api_url = "https://dadosabertos.ccee.org.br/api/3/action/package_show?id=pld_horario"

    try:
        print(f"Buscando link do PLD {year} na API da CCEE...")
        resp = c_requests.get(api_url, impersonate="chrome", timeout=30)

        if resp.status_code == 200:
            dados = resp.json()
            recursos = dados.get("result", {}).get("resources", [])
            
            # Procura o arquivo que tem o ano no nome
            link_download = None
            for r in recursos:
                nome = r.get("name", "").lower()
                if str(year) in nome:
                    link_download = r.get("url")
                    break

            if not link_download:
                print(f"Nao achei o arquivo de {year} na API da CCEE.")
                return False

            print(f"Baixando PLD de {year}...")
            return download_file(link_download, dest_path, use_impersonation=True, force=force)

        print(f"Erro ao acessar API da CCEE: {resp.status_code}")
        return False
    except Exception as e:
        print(f"Falha ao buscar PLD: {e}")
        return False


def fetch_energy_data(raw_data_dir, years=None, force=False):
    """
    Funcao principal que baixa os dados do ONS e da CCEE para os anos selecionados.
    """
    if years is None:
        years = [get_current_year()]
    elif isinstance(years, int):
        years = [years]
    else:
        years = list(years)

    os.makedirs(raw_data_dir, exist_ok=True)
    resultado = {}

    for ano in sorted(years):
        print(f"\n--- Baixando dados do ano {ano} ---")
        res_ano = {}

        # Links do ONS no Amazon S3
        ons_links = {
            "ons_ear": {
                "arquivo": f"ons_ear_daily_{ano}.csv",
                "url": f"https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ear_subsistema_di/EAR_DIARIO_SUBSISTEMA_{ano}.csv"
            },
            "ons_ena": {
                "arquivo": f"ons_ena_daily_{ano}.csv",
                "url": f"https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ena_subsistema_di/ENA_DIARIO_SUBSISTEMA_{ano}.csv"
            }
        }

        # Baixa EAR e ENA do ONS
        for chave, info in ons_links.items():
            caminho = os.path.join(raw_data_dir, info["arquivo"])
            ok = download_file(info["url"], caminho, force=force)
            res_ano[chave] = {"sucesso": ok, "path": caminho}
            if ok:
                print(f"Download concluido: {info['arquivo']}")
            else:
                print(f"Erro ao baixar: {info['arquivo']}")

        # Baixa PLD da CCEE
        pld_arquivo = f"ccee_pld_hourly_{ano}.csv"
        pld_caminho = os.path.join(raw_data_dir, pld_arquivo)
        pld_ok = fetch_ccee_pld_via_api(pld_caminho, year=ano, force=force)
        res_ano["ccee_pld"] = {"sucesso": pld_ok, "path": pld_caminho}

        resultado[ano] = res_ano

    return resultado