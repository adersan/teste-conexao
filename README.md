# AS Tech — Diagnóstico de conexão

Dashboard de diagnóstico de rede para Windows, desenvolvido em Python com Flet.

## Recursos

- Medição de latência, jitter, download e upload
- Seleção regional de servidores Speedtest
- Fallback automático pela rede Cloudflare
- Diagnóstico visual da qualidade da conexão
- Relógio em tempo real e histórico da última medição

## Executar

Execute `Executar_v11_Flet.bat`. O lançador verifica e instala as dependências:

- Python 3
- Flet
- speedtest-cli

Também é possível iniciar diretamente:

```powershell
python teste_rede_dashboard_v11_flet.py
```

## Gerar o instalador

Execute `build_installer.bat`. O pacote final será criado em:

```text
release\AS-Tech-Diagnostico-Setup-1.0.1.exe
```

O instalador é destinado ao Windows 64-bit e não exige Python no computador
do usuário.
