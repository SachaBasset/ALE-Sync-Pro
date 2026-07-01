#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ALE Sync Pro - CLI Version
Automated Subclipping for Avid Media Composer
Compatibility: Windows & macOS
"""

import sys
import re
import os

def tc_to_frames(tc, fps=25):
    """Convertit hh:mm:ss:ff ou hh:mm:ss.ff en nombre de frames absolu."""
    if not tc: return 0
    try:
        clean_tc = str(tc).strip().replace('.', ':')
        parts = clean_tc.split(':')
        if len(parts) != 4: return 0
        h, m, s, f = map(int, parts)
        return (h * 3600 * fps) + (m * 60 * fps) + (s * fps) + f
    except: return 0

def frames_to_tc(frames, fps=25):
    """Convertit un nombre de frames en Timecode Avid hh:mm:ss:ff."""
    h = int(frames // (3600 * fps))
    m = int((frames // (60 * fps)) % 60)
    s = int((frames // fps) % 60)
    f = int(frames % fps)
    return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"

def rename_for_subclip(audio_name, video_name):
    """Nettoyage nomenclature Cantar : '1024 07/t2' -> '1024/7-2 CAM A'."""
    name = audio_name.strip()
    name = name.replace("/t", "-").replace("/p", "-")
    name = re.sub(r'\s+', '/', name)
    name = name.replace("/0", "/") # Simplification (ex: 07 en 7)
    
    # Détection caméra (A ou B)
    prefix = video_name.split('_')[0]
    cam = "CAM A" if "A" in prefix.upper() else "CAM B"
    return f"{name} {cam}"

def process_ale(input_path):
    print(f"\n--- ALE SYNC PRO : ANALYSE ---")
    
    # Gestion des encodages (Avid PC utilise souvent UTF-16 ou Latin-1)
    lines = []
    encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']
    for enc in encodings:
        try:
            with open(input_path, 'r', encoding=enc) as f:
                lines = f.readlines()
            print(f"Encodage détecté : {enc}")
            break
        except: continue

    if not lines:
        print("Erreur : Impossible de lire le fichier. Vérifiez le format.")
        return

    header, columns, video_clips, audio_clips = [], [], [], []
    data_started, col_found = False, False
    
    for line in lines:
        raw = line.strip('\n\r')
        if not raw: continue
        if not data_started: header.append(line)
        
        if raw == "Column": col_found = True; continue
        if raw == "Data": data_started = True; continue
        
        if col_found and not data_started:
            columns = [c.strip() for c in raw.split('\t') if c.strip()]
            col_found = False; continue
            
        if data_started:
            values = raw.split('\t')
            clip = {columns[i]: values[i].strip() for i in range(min(len(columns), len(values)))}
            tracks = clip.get('Tracks', '').upper()
            
            # Calcul des frames pour l'intersection
            clip['_start_f'] = tc_to_frames(clip.get('Start'))
            clip['_end_f'] = tc_to_frames(clip.get('End'))
            
            if 'V' in tracks and 'A' not in tracks:
                video_clips.append(clip)
            elif 'A' in tracks and 'V' not in tracks:
                audio_clips.append(clip)

    print(f"Clips trouvés : {len(video_clips)} Vidéos, {len(audio_clips)} Sons")

    # Génération du fichier de sortie
    output_path = input_path.rsplit('.', 1)[0] + "_SUBCLIPS.ale"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        # Réécriture de l'entête original
        for line in header:
            if line.strip() == "Data": break
            f.write(line)
        f.write("Data\n")
        
        match_count = 0
        for v in video_clips:
            # Logique d'overlap strict
            match_a = next((a for a in audio_clips if a['_start_f'] < v['_end_f'] and a['_end_f'] > v['_start_f']), None)
            
            if match_a:
                # Intersection mathématique des plages
                final_start_f = max(v['_start_f'], match_a['_start_f'])
                final_end_f = min(v['_end_f'], match_a['_end_f'])
                
                sub_name = rename_for_subclip(match_a['Name'], v['Name'])
                
                row = []
                for col in columns:
                    if col == 'Name': row.append(sub_name)
                    elif col == 'Start': row.append(frames_to_tc(final_start_f))
                    elif col == 'End': row.append(frames_to_tc(final_end_f))
                    elif col == 'Tracks': row.append("VA1A2")
                    elif col == 'Soundroll': row.append(match_a.get('Soundroll') or match_a.get('Name'))
                    elif col == 'Camroll': row.append(v.get('Camroll') or v.get('Name'))
                    elif col == 'Tape': row.append(v.get('Tape') or v.get('Name'))
                    else: row.append(v.get(col, ""))
                
                f.write("\t".join(row) + "\n")
                match_count += 1
                print(f"MATCH : {sub_name}")

    print(f"\n--- TERMINÉ : {match_count} subclips générés ---")
    print(f"Fichier : {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ale_sync_pro.py mon_fichier.ale")
    else:
        process_ale(sys.argv[1])