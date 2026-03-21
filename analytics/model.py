import torch
import torch.nn as nn

# LSTM autoencoder for anomaly detection.
# encoder squashes the sequence into a hidden state,
# decoder tries to reconstruct it.
# high reconstruction error = something looks off.
class LSTMAutoencoder(nn.Module):

    def __init__(self, input_size=1, hidden_size=64, num_layers=2, dropout=0.2):
        super(LSTMAutoencoder, self).__init__()

        self.hidden_size = hidden_size
        self.num_layers  = num_layers

        self.encoder = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout
        )

        self.decoder = nn.LSTM(
            input_size=hidden_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout
        )

        self.output_layer = nn.Linear(hidden_size, input_size)

    def forward(self, x):
        batch_size, seq_len, _ = x.size()

        _, (hidden, cell) = self.encoder(x)

        decoder_input = hidden[-1].unsqueeze(1).repeat(1, seq_len, 1)

        decoder_out, _ = self.decoder(decoder_input, (hidden, cell))

        reconstruction = self.output_layer(decoder_out)
        return reconstruction
