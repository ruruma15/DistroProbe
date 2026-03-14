import torch
import torch.nn as nn


class LSTMAutoencoder(nn.Module):
    """
    LSTM Autoencoder for time-series anomaly detection.

    How it works:
      - Encoder compresses a sequence of latency readings into a hidden state
      - Decoder reconstructs the original sequence from that hidden state
      - If reconstruction error is high, the pattern is anomalous
      - Normal traffic = low error. Congestion spike = high error.

    This is the same architecture used in production anomaly detection
    systems at Netflix and LinkedIn.
    """

    def __init__(self, input_size=1, hidden_size=64, num_layers=2, dropout=0.2):
        super(LSTMAutoencoder, self).__init__()

        self.hidden_size = hidden_size
        self.num_layers  = num_layers

        # Encoder: compress sequence into latent representation
        self.encoder = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout
        )

        # Decoder: reconstruct sequence from latent representation
        self.decoder = nn.LSTM(
            input_size=hidden_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout
        )

        # Output projection back to original dimension
        self.output_layer = nn.Linear(hidden_size, input_size)

    def forward(self, x):
        batch_size, seq_len, _ = x.size()

        # Encode
        _, (hidden, cell) = self.encoder(x)

        # Repeat hidden state across sequence length for decoder input
        decoder_input = hidden[-1].unsqueeze(1).repeat(1, seq_len, 1)

        # Decode
        decoder_out, _ = self.decoder(decoder_input, (hidden, cell))

        # Project to output
        reconstruction = self.output_layer(decoder_out)
        return reconstruction
