#!/usr/bin/env python3
"""
Entrenamiento del wake word "Capitán" con openWakeWord.
Cubre pasos 1.12 (features), 1.13 (training) y 1.14 (export ONNX).

Uso:
    source ~/ai-env/bin/activate
    python wakeword/train_capitan.py
"""

import os
import sys
import glob
import logging
import numpy as np
import scipy.io.wavfile as wavfile
import scipy.signal
import torch

# Usar el repo clonado para tener train.py (no incluido en el paquete 0.4.0)
# Los modelos ONNX se pasan explícitamente desde el venv
sys.path.insert(0, os.path.expanduser("~/ai-lab/wakeword/openWakeWord"))
from openwakeword.utils import AudioFeatures
from openwakeword.train import Model

MELSPEC_MODEL  = os.path.expanduser("~/ai-env/lib/python3.13/site-packages/openwakeword/resources/models/melspectrogram.onnx")
EMBEDDING_MODEL = os.path.expanduser("~/ai-env/lib/python3.13/site-packages/openwakeword/resources/models/embedding_model.onnx")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

# ── Configuración ──────────────────────────────────────────────────────────────

POSITIVE_DIR = os.path.expanduser("~/ai-lab/wakeword/data/capitán/positive")
NEGATIVE_DIR = os.path.expanduser("~/ai-lab/wakeword/data/capitán/negative")
OUTPUT_DIR   = os.path.expanduser("~/ai-lab/wakeword/output")
MODEL_NAME   = "capitan"

TARGET_SR      = 16000
CLIP_SAMPLES   = 32000   # 2s — da input_shape (16, 96)
RESAMPLE_UP    = 320     # 22050 × 320/441 = 16000
RESAMPLE_DOWN  = 441
TRAIN_RATIO    = 0.8
BATCH_SIZE_FEATURES = 64
N_CPU          = min(8, os.cpu_count() or 1)
TRAIN_STEPS    = 10000

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ── Paso 1.12: Carga y extracción de features ──────────────────────────────────

def load_wav_clips(directory, pattern="*.wav"):
    paths = sorted(glob.glob(os.path.join(directory, pattern)))
    if not paths:
        raise FileNotFoundError(f"No se encontraron WAVs en {directory}")

    clips = []
    for path in paths:
        sr, data = wavfile.read(path)
        if data.ndim > 1:
            data = data[:, 0]

        # Resamplear de 22050Hz a 16000Hz
        if sr != TARGET_SR:
            data = data.astype(np.float32)
            data = scipy.signal.resample_poly(data, RESAMPLE_UP, RESAMPLE_DOWN)
            data = np.clip(data, -32768, 32767).astype(np.int16)

        # Centrar y pad/trim a CLIP_SAMPLES
        if len(data) >= CLIP_SAMPLES:
            start = (len(data) - CLIP_SAMPLES) // 2
            data = data[start:start + CLIP_SAMPLES]
        else:
            pad_total = CLIP_SAMPLES - len(data)
            pad_before = pad_total // 2
            pad_after = pad_total - pad_before
            data = np.pad(data, (pad_before, pad_after), mode="constant")

        clips.append(data)

    return np.array(clips, dtype=np.int16)


log.info("── Paso 1.12: Extracción de features ──")
log.info(f"Cargando positivos desde {POSITIVE_DIR}...")
pos_clips = load_wav_clips(POSITIVE_DIR)
log.info(f"  {len(pos_clips)} clips positivos cargados, shape={pos_clips.shape}")

log.info(f"Cargando negativos desde {NEGATIVE_DIR}...")
neg_clips = load_wav_clips(NEGATIVE_DIR)
log.info(f"  {len(neg_clips)} clips negativos cargados, shape={neg_clips.shape}")

log.info("Inicializando AudioFeatures (ONNX, CPU)...")
F = AudioFeatures(
    melspec_model_path=MELSPEC_MODEL,
    embedding_model_path=EMBEDDING_MODEL,
    ncpu=N_CPU,
    device="cpu",
)

log.info("Extrayendo embeddings de positivos...")
pos_features = F.embed_clips(pos_clips, batch_size=BATCH_SIZE_FEATURES)
log.info(f"  pos_features shape: {pos_features.shape}")

log.info("Extrayendo embeddings de negativos...")
neg_features = F.embed_clips(neg_clips, batch_size=BATCH_SIZE_FEATURES)
log.info(f"  neg_features shape: {neg_features.shape}")

# Guardar features
np.save(os.path.join(OUTPUT_DIR, "pos_features.npy"), pos_features)
np.save(os.path.join(OUTPUT_DIR, "neg_features.npy"), neg_features)
log.info(f"Features guardadas en {OUTPUT_DIR}")


# ── Paso 1.13: Training ────────────────────────────────────────────────────────

log.info("── Paso 1.13: Training ──")

INPUT_SHAPE = pos_features.shape[1:]  # (16, 96)
log.info(f"input_shape: {INPUT_SHAPE}")

# Split train/val
np.random.seed(42)
n_pos = len(pos_features)
n_neg = len(neg_features)

pos_idx = np.random.permutation(n_pos)
neg_idx = np.random.permutation(n_neg)

pos_train = pos_features[pos_idx[:int(n_pos * TRAIN_RATIO)]]
pos_val   = pos_features[pos_idx[int(n_pos * TRAIN_RATIO):]]
neg_train = neg_features[neg_idx[:int(n_neg * TRAIN_RATIO)]]
neg_val   = neg_features[neg_idx[int(n_neg * TRAIN_RATIO):]]

log.info(f"Train: {len(pos_train)} pos, {len(neg_train)} neg")
log.info(f"Val:   {len(pos_val)} pos, {len(neg_val)} neg")

# Calcular duración real de los negativos para val_set_hrs
# CLIP_SAMPLES / TARGET_SR segundos por clip
neg_duration_hrs = (len(neg_val) * CLIP_SAMPLES / TARGET_SR) / 3600
log.info(f"Duración val negativos: {neg_duration_hrs:.3f} horas")

# Construir DataLoaders
X_train_data = np.vstack([
    pos_train,
    neg_train[:len(neg_train)]
])
y_train_data = np.array(
    [1.0] * len(pos_train) + [0.0] * len(neg_train),
    dtype=np.float32
)

X_val_data = np.vstack([pos_val, neg_val])
y_val_data = np.array(
    [1.0] * len(pos_val) + [0.0] * len(neg_val),
    dtype=np.float32
)

train_dataset = torch.utils.data.TensorDataset(
    torch.from_numpy(X_train_data), torch.from_numpy(y_train_data)
)
val_dataset = torch.utils.data.TensorDataset(
    torch.from_numpy(X_val_data), torch.from_numpy(y_val_data)
)

# Batch generator con shuffle
def make_generator(dataset, batch_size=128):
    loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True)
    while True:
        for batch in loader:
            yield batch

X_train = make_generator(train_dataset)
X_val_loader = torch.utils.data.DataLoader(val_dataset, batch_size=len(val_dataset))

# DataLoader de falsos positivos (negativos de val)
fp_data = torch.from_numpy(neg_val)
fp_labels = torch.zeros(len(neg_val), dtype=torch.float32)
fp_loader = torch.utils.data.DataLoader(
    torch.utils.data.TensorDataset(fp_data, fp_labels),
    batch_size=len(neg_val)
)

# Crear y entrenar modelo
oww = Model(
    n_classes=1,
    input_shape=INPUT_SHAPE,
    model_type="dnn",
    layer_dim=128,
    n_blocks=1,
)

val_steps = np.linspace(TRAIN_STEPS * 0.5, TRAIN_STEPS, 20).astype(np.int64).tolist()
weights = np.linspace(1, 100, TRAIN_STEPS).tolist()

log.info(f"Entrenando {TRAIN_STEPS} steps...")
oww.train_model(
    X=X_train,
    X_val=X_val_loader,
    false_positive_val_data=fp_loader,
    max_steps=TRAIN_STEPS,
    negative_weight_schedule=weights,
    val_steps=val_steps,
    warmup_steps=TRAIN_STEPS // 5,
    hold_steps=TRAIN_STEPS // 3,
    lr=0.0001,
    val_set_hrs=max(neg_duration_hrs, 0.01),
)


# ── Paso 1.14: Export ONNX ─────────────────────────────────────────────────────

log.info("── Paso 1.14: Export ONNX ──")
import onnx
import shutil

onnx_path = os.path.join(OUTPUT_DIR, MODEL_NAME + ".onnx")

# Exportar con PyTorch
oww.model.eval()
oww.export_model(model=oww.model, model_name=MODEL_NAME, output_dir=OUTPUT_DIR)
log.info(f"Modelo exportado a {onnx_path}")

# Consolidar en un único archivo (el export puede generar .onnx + .onnx.data)
model_proto = onnx.load(onnx_path)
final_path = os.path.expanduser(f"~/.local/share/wakeword/{MODEL_NAME}.onnx")
os.makedirs(os.path.dirname(final_path), exist_ok=True)
onnx.save_model(model_proto, final_path, save_as_external_data=False)
log.info(f"Modelo consolidado en {final_path} ({os.path.getsize(final_path)//1024}KB)")

log.info("✓ Training completo")
