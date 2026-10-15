#!/usr/bin/env bash
# Read-only disk survey of /home/hari on big-machine.
cd ~
OUT=~/research/embedgemma/du_report.txt
{
echo "=== df ==="; df -h / | tail -1
echo; echo "=== top-level dirs (apparent usage, incl. dotdirs) ==="
du -xsh ~/* ~/.[!.]* 2>/dev/null | sort -rh | head -45
echo; echo "=== single files > 1 GB (top 80) ==="
find ~ -xdev -type f -size +1G -printf "%s\t%TY-%Tm-%Td\t%p\n" 2>/dev/null | sort -rn | head -80 | awk -F'\t' '{printf "%7.1f G  %s  %s\n", $1/1073741824, $2, $3}'
echo; echo "=== conda envs / pkgs ==="
du -xsh ~/miniconda3/envs/* ~/miniconda3/pkgs 2>/dev/null | sort -rh
echo; echo "=== caches ==="
du -xsh ~/.cache/* 2>/dev/null | sort -rh | head -15
echo; echo "=== hf hub models ==="
du -xsh ~/.cache/huggingface/hub/* 2>/dev/null | sort -rh | head -30
echo; echo "=== trash / tmp ==="
du -xsh ~/.local/share/Trash 2>/dev/null; du -xsh /tmp 2>/dev/null
echo; echo "DU_DONE"
} > "$OUT" 2>&1
