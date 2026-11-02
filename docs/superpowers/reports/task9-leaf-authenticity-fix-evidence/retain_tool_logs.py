from pathlib import Path
import shutil

own = Path(__file__).parent
base = Path("/Users/bytedance/Library/Application Support/Trae CN/ModularData/ai-agent/command-execution")
target = own / "tool-raw"
target.mkdir(exist_ok=True)
for command_id in (
    "5005873266c5bfb16ae2f138f9e8a169",
    "486b220a203d11b6074d5c3fb33cc393",
    "6e8dc76ebebf933c4596f8d1fc07e999",
    "0f42fef4eb490624ebf94750586d8326",
):
    source = base / command_id / "output.log"
    assert source.is_file(), str(source)
    dest = target / (command_id + ".log")
    assert not dest.exists()
    shutil.copy2(source, dest)
