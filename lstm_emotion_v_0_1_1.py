# -*- coding: utf-8 -*-
"""LSTM_emotion v.0.1.1.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1eN6aLGXRysovp6Z5Mz_jItj9UsbUTB_a

LSTM
"""

import os
import zipfile
import gdown
import numpy as np
import librosa
import tensorflow as tf
import tensorflow_hub as hub
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns
from tensorflow.keras.preprocessing.sequence import pad_sequences

# 1. Load YAMNet model
yamnet_model = hub.load('https://tfhub.dev/google/yamnet/1')

# 2. Function to preprocess audio files
def preprocess_audio(file_path):
    audio, sr = librosa.load(file_path, sr=16000)  # Resample to 16kHz
    return audio

# 3. Function to extract embeddings from YAMNet (mengembalikan sequence embeddings)
def extract_embeddings(audio):
    # Menghasilkan tuple: (scores, embeddings, spectrogram)
    _, embeddings, _ = yamnet_model(audio)
    return embeddings.numpy()  # shape: (num_frames, embedding_dim)

# 4. Function for audio augmentation
def augment_audio(audio, sr):
    # Time Stretching
    audio_stretched = librosa.effects.time_stretch(audio, rate=1.1)
    # Pitch Shifting
    audio_shifted = librosa.effects.pitch_shift(audio, sr=sr, n_steps=2)
    # Tambahkan Noise
    noise = np.random.normal(0, 0.01, len(audio))
    audio_noisy = audio + noise
    return [audio_stretched, audio_shifted, audio_noisy]

# 5. Download and extract the dataset from Google Drive
dataset_url = "https://drive.google.com/uc?id=1OdGtIQ4ZGhauIHMzuLt7hrMHARfVZeA5"
dataset_zip = "ravdess.zip"
gdown.download(dataset_url, dataset_zip, quiet=False)

with zipfile.ZipFile(dataset_zip, 'r') as zip_ref:
    zip_ref.extractall("ravdess_data")

DATASET_PATH = "ravdess_data"

# 6. Ekstraksi fitur dan label
X, y = [], []
for root, _, files in os.walk(DATASET_PATH):
    for file in files:
        if file.endswith('.wav'):
            file_path = os.path.join(root, file)
            audio = preprocess_audio(file_path)
            embedding_seq = extract_embeddings(audio)  # sequence embeddings dengan shape (T, D)
            # Ambil label dari nama file (misalnya: '03-01-03-02-01-01-01.wav', label berada di indeks ke-2)
            label = file.split('-')[2]
            X.append(embedding_seq)
            y.append(label)

            # Augmentasi data
            augmented_audios = augment_audio(audio, sr=16000)
            for aug_audio in augmented_audios:
                aug_embedding_seq = extract_embeddings(aug_audio)
                X.append(aug_embedding_seq)
                y.append(label)

print(f"Total data setelah augmentasi: {len(X)} samples")

# 7. Padding sequences agar semua sample memiliki panjang yang sama
X_padded = pad_sequences(X, padding='post', dtype='float32')
print("Shape after padding:", X_padded.shape)  # (num_samples, max_length, embedding_dim)

# 8. Opsional: Normalisasi fitur
num_samples, max_len, emb_dim = X_padded.shape
X_reshaped = X_padded.reshape(-1, emb_dim)
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_reshaped)
X_scaled = X_scaled.reshape(num_samples, max_len, emb_dim)

# 9. Encode label menjadi angka
encoder = LabelEncoder()
y_encoded = encoder.fit_transform(y)

# 10. Split data menjadi training dan testing
X_train, X_test, y_train, y_test = train_test_split(X_scaled, y_encoded, test_size=0.2, random_state=42)
print(f"Training samples: {len(X_train)}, Testing samples: {len(X_test)}")

# 11. Membangun model LSTM
model = tf.keras.Sequential([
    # Masking layer untuk mengabaikan padding (mask_value=0 sesuai dengan padding yang digunakan)
    tf.keras.layers.Masking(mask_value=0., input_shape=(max_len, emb_dim)),
    tf.keras.layers.LSTM(64, return_sequences=True),
    tf.keras.layers.LSTM(32),
    tf.keras.layers.Dense(32, activation='relu'),
    tf.keras.layers.Dropout(0.5),
    tf.keras.layers.Dense(len(np.unique(y_encoded)), activation='softmax')
])

# 12. Kompilasi model
model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
              loss='sparse_categorical_crossentropy',
              metrics=['accuracy'])
model.summary()

# 13. Latih model
history = model.fit(
    X_train,
    y_train,
    epochs=100,
    batch_size=32,
    validation_data=(X_test, y_test),
    callbacks=[
        tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True),
        tf.keras.callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.2, patience=5, min_lr=0.0001)
    ]
)

# 14. Evaluasi model
loss, accuracy = model.evaluate(X_test, y_test)
print(f"Test Accuracy: {accuracy:.2f}")

# 15. Visualisasi Confusion Matrix
predictions = np.argmax(model.predict(X_test), axis=1)
conf_matrix = confusion_matrix(y_test, predictions)

plt.figure(figsize=(10, 8))
sns.heatmap(conf_matrix, annot=True, fmt='d', cmap='Blues',
            xticklabels=encoder.classes_, yticklabels=encoder.classes_)
plt.title('Confusion Matrix')
plt.xlabel('Predicted Labels')
plt.ylabel('True Labels')
plt.show()

from IPython.display import Audio, display

def predict_emotion_with_accuracy(file_path):
    # Preprocess file audio
    audio = preprocess_audio(file_path)
    # Ekstrak sequence embeddings
    embedding_seq = extract_embeddings(audio)  # shape: (T, emb_dim)

    # Padding sequence agar sesuai dengan max_len yang digunakan saat training
    padded_seq = pad_sequences([embedding_seq], maxlen=max_len, padding='post', dtype='float32')

    # Normalisasi menggunakan scaler yang sama (reshape dulu ke 2D, transform, lalu kembalikan ke 3D)
    padded_seq_scaled = scaler.transform(padded_seq.reshape(-1, emb_dim)).reshape(1, max_len, emb_dim)

    # Lakukan prediksi menggunakan model yang telah dilatih
    prediction = model.predict(padded_seq_scaled)
    predicted_label = encoder.inverse_transform([np.argmax(prediction)])[0]

    # Map numerical labels ke kategori emosi
    emotion_map = {
        '01': 'neutral',
        '02': 'calm',
        '03': 'happy',
        '04': 'sad',
        '05': 'angry',
        '06': 'fearful',
        '07': 'disgust',
        '08': 'surprised'
    }

    emotion_result = emotion_map.get(predicted_label, "Unknown Emotion")
    prediction_accuracy = np.max(prediction) * 100  # Akurasi prediksi dalam persentase

    return emotion_result, prediction_accuracy

# Allow user to input the file path
input_file = input("Enter the path to your audio file: ")

# Prediksi emosi dan tampilkan hasil beserta akurasi
try:
    print("Playing the input audio...")
    display(Audio(input_file))  # Memutar file audio yang diinput user

    predicted_emotion, acc = predict_emotion_with_accuracy(input_file)
    print(f"Predicted Emotion: {predicted_emotion}")
    print(f"Prediction Accuracy: {acc:.2f}%")
except Exception as e:
    print(f"Error occurred: {e}")