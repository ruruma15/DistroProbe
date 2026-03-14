import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from model import LSTMAutoencoder


class AnomalyTrainer:
    """
    Trains the LSTM Autoencoder and scores anomalies using
    reconstruction error (MSE between input and reconstructed output).
    """

    def __init__(self, seq_len=30, hidden_size=64, num_layers=2,
                 lr=0.001, epochs=50, batch_size=32):
        self.seq_len    = seq_len
        self.epochs     = epochs
        self.batch_size = batch_size
        self.device     = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.threshold  = None
        self.mean       = 0.0
        self.std        = 1.0

        self.model = LSTMAutoencoder(
            input_size=1,
            hidden_size=hidden_size,
            num_layers=num_layers
        ).to(self.device)

        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)
        self.criterion = nn.MSELoss()

    def _normalize(self, data):
        self.mean = np.mean(data)
        self.std  = np.std(data) + 1e-8
        return (data - self.mean) / self.std

    def _make_sequences(self, data):
        sequences = []
        for i in range(len(data) - self.seq_len):
            sequences.append(data[i:i + self.seq_len])
        return np.array(sequences)

    def train(self, latency_values: list):
        if len(latency_values) < self.seq_len + 10:
            print(f"[Trainer] Not enough data to train ({len(latency_values)} samples, need {self.seq_len + 10})")
            return False

        data       = np.array(latency_values, dtype=np.float32)
        normalized = self._normalize(data)
        sequences  = self._make_sequences(normalized)

        X      = torch.FloatTensor(sequences).unsqueeze(-1).to(self.device)
        loader = DataLoader(TensorDataset(X), batch_size=self.batch_size, shuffle=True)

        self.model.train()
        for epoch in range(self.epochs):
            total_loss = 0
            for (batch,) in loader:
                self.optimizer.zero_grad()
                output = self.model(batch)
                loss   = self.criterion(output, batch)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                self.optimizer.step()
                total_loss += loss.item()

            if (epoch + 1) % 10 == 0:
                print(f"[Trainer] Epoch {epoch+1}/{self.epochs} | loss={total_loss/len(loader):.6f}")

        # Set anomaly threshold = mean reconstruction error + 3 std deviations
        self.threshold = self._compute_threshold(X)
        print(f"[Trainer] Training complete. Anomaly threshold={self.threshold:.6f}")
        return True

    def _compute_threshold(self, X):
        self.model.eval()
        with torch.no_grad():
            errors = []
            for i in range(len(X)):
                x      = X[i].unsqueeze(0)
                output = self.model(x)
                error  = self.criterion(output, x).item()
                errors.append(error)
        return float(np.mean(errors) + 3 * np.std(errors))

    def score(self, latency_window: list):
        if len(latency_window) < self.seq_len:
            return 0.0, False

        data       = np.array(latency_window[-self.seq_len:], dtype=np.float32)
        normalized = (data - self.mean) / (self.std + 1e-8)
        x          = torch.FloatTensor(normalized).unsqueeze(0).unsqueeze(-1).to(self.device)

        self.model.eval()
        with torch.no_grad():
            output = self.model(x)
            error  = self.criterion(output, x).item()

        is_anomaly = self.threshold is not None and error > self.threshold
        score      = min(error / (self.threshold + 1e-8), 1.0) if self.threshold else 0.0
        return score, is_anomaly

    def is_trained(self):
        return self.threshold is not None
