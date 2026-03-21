import sys
import os

os.environ['MODO_FLUJO'] = 'full'
os.environ['ARCHIVO_LOCAL_FW'] = 'WA.v8.7.19.48279.250811.0636.bin'
os.environ['BACKUP_CFG'] = 'WA-28704EB63776.cfg'

sys.path.append(os.getcwd())
import configuracion_completa_antenas2

try:
    configuracion_completa_antenas2.run_all(range_start=11, range_end=11, backup_cfg='WA-28704EB63776.cfg', archivo_local_fw='WA.v8.7.19.48279.250811.0636.bin')
except Exception as e:
    import traceback
    traceback.print_exc()
