"""
autoencoder.py - PyTorch autoencoder for anomaly detection
Architecture: 24→12→6→12→24 with ReLU activation and 0.2 dropout
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import numpy as np
from typing import Tuple
import pickle


class CreditAutoencoder(nn.Module):
    """Autoencoder for credit profile anomaly detection"""

    def __init__(self, input_dim: int = 24):
        super(CreditAutoencoder, self).__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 12),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(12, 6),
            nn.ReLU(),
        )
        self.decoder = nn.Sequential(
            nn.Linear(6, 12),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(12, input_dim),
            nn.Sigmoid(),  # Output normalized 0-1
        )

    def forward(self, x):
        encoded = self.encoder(x)
        decoded = self.decoder(encoded)
        return decoded, encoded

    def encode(self, x):
        return self.encoder(x)


def train_autoencoder(
    X_train: np.ndarray,
    X_val: np.ndarray,
    epochs: int = 50,
    batch_size: int = 32,
    learning_rate: float = 0.001,
    device: str = "cpu",
) -> Tuple[CreditAutoencoder, float, float]:
    """
    Train autoencoder on NORMAL profiles only
    Returns: (trained_model, reconstruction_error_mean, reconstruction_error_std)
    """
    model = CreditAutoencoder(input_dim=X_train.shape[1]).to(device)
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)

    # Convert to tensors
    X_train_tensor = torch.from_numpy(X_train).float().to(device)
    X_val_tensor = torch.from_numpy(X_val).float().to(device)

    train_dataset = TensorDataset(X_train_tensor)
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)

    best_val_loss = float("inf")
    patience_counter = 0
    patience = 5

    for epoch in range(epochs):
        # Training
        model.train()
        train_loss = 0
        for batch in train_loader:
            X_batch = batch[0]
            optimizer.zero_grad()
            reconstructed, _ = model(X_batch)
            loss = criterion(reconstructed, X_batch)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()

        train_loss /= len(train_loader)

        # Validation
        model.eval()
        with torch.no_grad():
            val_reconstructed, _ = model(X_val_tensor)
            val_loss = criterion(val_reconstructed, X_val_tensor).item()

        if (epoch + 1) % 10 == 0:
            print(f"Epoch {epoch+1}/{epochs} | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f}")

        # Early stopping
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"Early stopping at epoch {epoch+1}")
                break

    # Compute reconstruction error statistics on validation set
    model.eval()
    with torch.no_grad():
        val_reconstructed, _ = model(X_val_tensor)
        val_errors = (val_reconstructed - X_val_tensor).pow(2).mean(dim=1).cpu().numpy()

    error_mean = float(np.mean(val_errors))
    error_std = float(np.std(val_errors))

    print(f"✓ Autoencoder trained. Reconstruction error (val): {error_mean:.4f} ± {error_std:.4f}")

    return model, error_mean, error_std


def get_reconstruction_error(model: CreditAutoencoder, X: np.ndarray, device: str = "cpu") -> np.ndarray:
    """
    Compute reconstruction error for samples
    Lower error = more normal, Higher error = more anomalous
    """
    model.eval()
    X_tensor = torch.from_numpy(X).float().to(device)

    with torch.no_grad():
        reconstructed, _ = model(X_tensor)
        errors = (reconstructed - X_tensor).pow(2).mean(dim=1).cpu().numpy()

    return errors


def save_model(model: CreditAutoencoder, path: str):
    """Save autoencoder to file"""
    torch.save(model.state_dict(), path)
    print(f"✓ Autoencoder saved to {path}")


def load_model(path: str, device: str = "cpu") -> CreditAutoencoder:
    """Load autoencoder from file"""
    model = CreditAutoencoder()
    model.load_state_dict(torch.load(path, map_location=device))
    model.to(device)
    print(f"✓ Autoencoder loaded from {path}")
    return model


# Quick test
if __name__ == "__main__":
    # Generate synthetic normal data
    X_train = np.random.randn(700, 24).astype(np.float32)
    X_val = np.random.randn(100, 24).astype(np.float32)

    # Normalize to 0-1
    X_train = (X_train - X_train.min()) / (X_train.max() - X_train.min() + 1e-6)
    X_val = (X_val - X_val.min()) / (X_val.max() - X_val.min() + 1e-6)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")

    model, error_mean, error_std = train_autoencoder(X_train, X_val, epochs=50, device=device)

    # Test reconstruction error
    test_data = X_val[:5]
    errors = get_reconstruction_error(model, test_data, device=device)
    print(f"Sample reconstruction errors: {errors}")
