import sys, json
sys.path.insert(0, r"C:\Sofistik workflow\sofistik-mcp")
from sofistik_mcp import cdbio, results as R, install, config
CDB = r"C:\Sofistik workflow\26016-member-check\v19\26016_check_v19.cdb"
def open_cdb(path=CDB):
    st = config.load_settings(r"C:\Sofistik workflow\sofistik-mcp\settings.json")
    info = install.find(st)
    daten = cdbio.load_daten(info.get("daten"))
    return cdbio.Cdb(path, info), daten
