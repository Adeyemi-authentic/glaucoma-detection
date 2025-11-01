import os
import io
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import transforms
from PIL import Image
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware

# Define CNN
class GlaucomaCNN(nn.Module):
    def __init__(self):
        super(GlaucomaCNN, self).__init__()
        self.conv_layers = nn.Sequential(
            nn.Conv2d(3, 16, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2, 2),
            nn.Conv2d(16, 32, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2, 2)
        )
        self.fc_layers = nn.Sequential(
            nn.Flatten(),
            nn.Linear(32 * 32 * 32, 128),
            nn.ReLU(),
            nn.Linear(128, 2)
        )

    def forward(self, x):
        x = self.conv_layers(x)
        x = self.fc_layers(x)
        return x

# Class order must match your training label order
CLASS_NAMES = ['GON+', 'GON-']

# Setup device
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Load model
model = GlaucomaCNN().to(device)
model.load_state_dict(torch.load("glaucoma.pth", map_location=device))
model.eval()

# Define transforms
transform = transforms.Compose([
    transforms.Resize((128, 128)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.5, 0.5, 0.5],
                         std=[0.5, 0.5, 0.5])
])

# Initialize FastAPI app
app = FastAPI(title="Glaucoma Detection API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "Welcome to Glaucoma Classification API"}

@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    try:
        image_bytes = await file.read()
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        image = transform(image).unsqueeze(0).to(device)

        with torch.no_grad():
            outputs = model(image)
            probs = F.softmax(outputs, dim=1)
            predicted_idx = torch.argmax(probs, dim=1).item()
            confidence = probs[0][predicted_idx].item()

        return {
            "filename": file.filename,
            "predicted_class": CLASS_NAMES[predicted_idx],
            "confidence": round(confidence * 100, 2)
        }

    except Exception as e:
        return {"error": str(e)}
