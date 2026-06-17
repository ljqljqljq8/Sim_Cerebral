
from pathlib import Path
import shutil
import time

solver_dir = Path(__file__).resolve().parent
root = solver_dir.parents[3]
log = solver_dir / 'monitor_disk_production_save20.log'
stop_file = solver_dir / 'STOP_SIM'
min_free_gib = 5.0
while True:
    usage = shutil.disk_usage(root)
    free_gib = usage.free / 1024**3
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} free_gib={free_gib:.2f}\n"
    with log.open('a') as stream:
        stream.write(line)
    if free_gib < min_free_gib:
        stop_file.write_text(f"Requested by disk monitor: free_gib={free_gib:.2f} below {min_free_gib:.2f}\n")
        with log.open('a') as stream:
            stream.write('STOP_SIM written due to low disk space\n')
        break
    time.sleep(60)
