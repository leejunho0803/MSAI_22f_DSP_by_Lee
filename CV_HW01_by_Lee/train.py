# -*- coding: utf-8 -*-
"""train.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/15bxI4QgOFnmNYu7ZN2suDbqVgVoV3DWL
"""

import matplotlib.pyplot as plt
import numpy as np
import torch
import math
from torch import nn
from torch.nn import functional as F

def conv3x3(in_planes, out_planes, stride=1):
    """3x3 convolution with padding"""
    return nn.Conv2d(in_planes, out_planes, kernel_size=3, stride=stride, padding=1, bias=False)


def conv1x1(in_planes, out_planes, stride=1):
    """1x1 convolution"""
    return nn.Conv2d(in_planes, out_planes, kernel_size=1, stride=stride, bias=False)


class ResidualBlock(nn.Module):
    def __init__(self, inplanes, planes, stride=1, downsample=None, norm_layer=None):
        super(ResidualBlock, self).__init__()
        if norm_layer is None:
            norm_layer = nn.BatchNorm2d
        # Both self.conv1 and self.downsample layers downsample the input when stride != 1
        self.conv1 = conv3x3(inplanes, planes, stride)
        self.bn1 = norm_layer(planes)
        self.relu1 = nn.LeakyReLU()
        self.conv2 = conv3x3(planes, planes)
        self.bn2 = norm_layer(planes)
        self.relu2 = nn.LeakyReLU()
        self.downsample = downsample
        self.stride = stride

    def forward(self, x):
        identity = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu1(out)

        out = self.conv2(out)
        out = self.bn2(out)

        if self.downsample is not None:
            identity = self.downsample(x)
        out += identity
        out = self.relu2(out)

        return out

class BaseResNet(nn.Sequential):
    def __init__(self, block: nn.Module, layers, num_classes, norm_layer=None):
        super(BaseResNet, self).__init__()
        if norm_layer is None:
            norm_layer = nn.BatchNorm2d
        self._norm_layer = norm_layer

        self.inplanes = 64
        self.conv1 = nn.Conv2d(3, self.inplanes, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn1 = norm_layer(self.inplanes)
        self.relu = nn.ReLU(inplace=True)
        self.maxpool = nn.MaxPool2d(kernel_size=2)
        self.layer1 = self._make_layer(block, self.inplanes, layers[0])
        self.layer2 = self._make_layer(block, self.inplanes * 2, layers[1], stride=2)
        self.layer3 = self._make_layer(block, self.inplanes * 4, layers[2], stride=2)
        self.avgpool = nn.AdaptiveAvgPool2d((1, 1))
        self.fc = nn.Sequential(nn.Dropout(p=0.3), nn.Linear(self.inplanes, num_classes))

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode="fan_out", nonlinearity="relu")
            elif isinstance(m, (nn.BatchNorm2d, nn.GroupNorm)):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)

    def _make_layer(self, block, planes, blocks, stride=1):
        norm_layer = self._norm_layer
        downsample = None
        if stride != 1:
            downsample = nn.Sequential(
                conv1x1(self.inplanes, planes, stride),
                norm_layer(planes),
            )

        layers = []
        layers.append(block(self.inplanes, planes, stride, downsample, norm_layer))
        self.inplanes = planes
        for _ in range(1, blocks):
            layers.append(block(self.inplanes, planes, norm_layer=norm_layer))

        return nn.Sequential(*layers)

    def forward(self, x):
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)
        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)

        x = self.avgpool(x)
        x = torch.flatten(x, 1)
        x = self.fc(x)

        return x

class ConvBlock(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size=3, stride=1, padding=1, bias=False):
        super(ConvBlock, self).__init__()
        self.conv = nn.Conv2d(
            in_channels, out_channels, kernel_size, stride=stride, padding=padding, bias=False
        )
        self.relu = nn.LeakyReLU()  # max(x, neg_slope * x)
        self.bn = nn.BatchNorm2d(out_channels)

    def forward(self, in_tensor):
        out = self.conv(in_tensor)
        out = self.relu(self.bn(out))
        return out


class BaseModel(nn.Module):
    def __init__(self, num_classes):
        super(BaseModel, self).__init__()
        self.num_classes = num_classes

        self.in_preproc = nn.Sequential(ConvBlock(3, 64), nn.MaxPool2d((2, 2)))
        self.features = nn.Sequential(
            ConvBlock(64, 64),
            ConvBlock(64, 64),
            nn.MaxPool2d((2, 2)),
            ConvBlock(64, 128),
            ConvBlock(128, 128),
            nn.MaxPool2d((2, 2)),
            ConvBlock(128, 128),
            nn.AdaptiveAvgPool2d(1),
        )
        self.classifier = nn.Sequential(
            nn.Dropout(p=0.25),
            nn.Linear(128, 128),
            nn.ReLU(inplace=True),
            nn.Linear(128, self.num_classes),
        )

    def forward(self, in_tensor):
        x = self.in_preproc(in_tensor)
        x = self.features(x)
        feat = torch.flatten(x, 1)
        logits = self.classifier(feat)
        return logits


class Bottleneck(nn.Module):
    def __init__(self, in_planes, growth_rate):
        super(Bottleneck, self).__init__()
        self.bn1 = nn.BatchNorm2d(in_planes)
        self.conv1 = nn.Conv2d(in_planes, 4 * growth_rate, kernel_size=1, bias=False)
        self.relu1 = nn.LeakyReLU()
        self.bn2 = nn.BatchNorm2d(4 * growth_rate)
        self.conv2 = nn.Conv2d(4 * growth_rate, growth_rate, kernel_size=3, padding=1, bias=False)
        self.relu2 = nn.LeakyReLU()

    def forward(self, x):
        out = self.conv1(self.bn1(self.relu1(x)))
        out = self.conv2(self.bn2(self.relu2(out)))
        out = torch.cat([out, x], 1)
        return out

class Transition(nn.Module):
    def __init__(self, in_planes, out_planes):
        super(Transition, self).__init__()
        self.bn = nn.BatchNorm2d(in_planes)
        self.conv = nn.Conv2d(in_planes, out_planes, kernel_size=1, bias=False)
        self.relu = nn.LeakyReLU()

    def forward(self, x):
        out = self.conv(self.bn(self.relu(x)))
        out = F.avg_pool2d(out, 2)
        return out

class DenseBlock(nn.Module):
    def __init__(self, in_planes, growth_rate):
        super(Bottleneck, self).__init__()
        self.bn1 = nn.BatchNorm2d(in_planes)
        self.conv1 = nn.Conv2d(4 * growth_rate, growth_rate, kernel_size=3, padding=1, bias=False)
        self.relu1 = nn.LeakyReLU()

    def forward(self, x):
        out = self.conv1(self.bn1(self.relu1(out)))
        out = torch.cat([out, x], 1)
        return out

class DenseNet(nn.Module):
    def __init__(self, block, nblocks, growth_rate=12, reduction=0.5, num_classes=10):
        super(DenseNet, self).__init__()
        self.growth_rate = growth_rate

        num_planes = 2 * growth_rate
        self.conv1 = nn.Conv2d(3, num_planes, kernel_size=3, padding=1, bias=False)

        self.dense1 = self._make_dense_layers(block, num_planes, nblocks[0])
        num_planes += nblocks[0] * growth_rate
        out_planes = int(math.floor(num_planes * reduction))
        self.trans1 = Transition(num_planes, out_planes)
        num_planes = out_planes

        self.dense2 = self._make_dense_layers(block, num_planes, nblocks[1])
        num_planes += nblocks[1] * growth_rate
        out_planes = int(math.floor(num_planes * reduction))
        self.trans2 = Transition(num_planes, out_planes)
        num_planes = out_planes

        self.dense3 = self._make_dense_layers(block, num_planes, nblocks[2])
        num_planes += nblocks[2] * growth_rate
        out_planes = int(math.floor(num_planes * reduction))
        self.trans3 = Transition(num_planes, out_planes)
        num_planes = out_planes

        self.dense4 = self._make_dense_layers(block, num_planes, nblocks[3])
        num_planes += nblocks[3] * growth_rate

        self.bn = nn.BatchNorm2d(num_planes)
        self.linear = nn.Linear(num_planes, num_classes)
        self.gap = nn.AdaptiveAvgPool2d((1, 1))

    def _make_dense_layers(self, block, in_planes, nblock):
        layers = []
        for i in range(nblock):
            layers.append(block(in_planes, self.growth_rate))
            in_planes += self.growth_rate
        return nn.Sequential(*layers)

    def forward(self, x):
        out = self.conv1(x)
        out = self.trans1(self.dense1(out))
        out = self.trans2(self.dense2(out))
        out = self.trans3(self.dense3(out))
        out = self.dense4(out)
        out = self.gap(F.relu(self.bn(out)))
        out = torch.flatten(out, 1)
        out = self.linear(out)
        return out

import os


# Catalyst uses multiple GPUs via DataParallel, we don't need it for now
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

# Commented out IPython magic to ensure Python compatibility.
# %%capture
# 
# ! pip install torchinfo
# ! pip install -U catalyst
# ! pip install onnx onnxruntime

import catalyst
catalyst.__version__

import matplotlib.pyplot as plt
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from torchvision import datasets
import numpy as np
from torchvision import datasets, transforms
from torch.utils.data import DataLoader
import torch
from sklearn.metrics import accuracy_score

"""#Preprocess"""

def preprocess(data_path):
    train_ds = datasets.CIFAR10(data_path, train=True, download=True)
    val_ds = datasets.CIFAR10(data_path, train=False, download=True)

    print(f"Train / val size: {len(train_ds)} / {len(val_ds)}")

    num_classes = len(train_ds.classes)
    print(f"num_classes: {num_classes}")

    print("Training classes: ", train_ds.classes)
    print("Validation classes: ", val_ds.classes)

    # let's use ImageNet mean and std values for image pixel values
    means = np.array((0.4914, 0.4822, 0.4465))
    stds = np.array((0.2023, 0.1994, 0.2010))

    base_transforms = [transforms.ToTensor(), transforms.Normalize(means, stds)]
    augmented_transforms = [
        # add your own augmentations here
        transforms.RandomCrop(32, padding=4, padding_mode="reflect"),
        transforms.RandomHorizontalFlip(),
        transforms.ColorJitter(hue=0.01, brightness=0.3, contrast=0.3, saturation=0.3),
    ]
    augmented_transforms += base_transforms

    transform_basic = transforms.Compose(base_transforms)
    transform_augment = transforms.Compose(augmented_transforms)

    train_ds = datasets.CIFAR10("./cifar10", train=True, download=True, transform=transform_augment)
    val_ds = datasets.CIFAR10("./cifar10", train=False, download=True, transform=transform_basic)


    return train_ds, val_ds

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
batch_size = 256
train_ds, val_ds = preprocess("./cifar10")
num_classes = len(train_ds.classes)
train_batch_gen = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
val_batch_gen = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
loaders = {"train": train_batch_gen, "valid": val_batch_gen}
img_batch, label_batch = next(iter(train_batch_gen))
print(f"Label tensor size: {label_batch.size()}")
print(f"Batch tensor size [B, C, H, W] = {img_batch.size()}")
print(f"Batch tensor range: min = {img_batch.min().item():.4f} max = {img_batch.max().item():.4f} ")

"""#Training"""

from torchinfo import summary
import matplotlib.pyplot as plt
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
import catalyst
#from model import ConvBlock, BaseModel, DenseNet, Bottleneck, BaseResNet, ResidualBlock
from typing import Dict
from catalyst.core.logger import ILogger
from catalyst.loggers.console import ConsoleLogger
from catalyst import dl
import os

def cifar_model_summary(model, device):
    col_names = ("output_size", "output_size", "num_params", "mult_adds")
    return summary(model, (1, 3, 32, 32), device=device, col_names=col_names)

def _format_metrics(dct: Dict):
    return " | ".join([f"{k}: {float(dct[k]):.03}" for k in sorted(dct.keys())])

def training():

    class CustomLogger(ConsoleLogger):
        """Custom console logger for parameters and metrics.
        Output the metric into the console during experiment.

        Note:
            We inherit ConsoleLogger to overwrite default Catalyst logging behaviour
        """
        def log_metrics(self, metrics: Dict[str, float],scope: str,runner: "IRunner",) -> None:
            """Logs loader and epoch metrics to stdout."""
            if scope == "loader":
                prefix = f"{runner.loader_key} ({runner.epoch_step}/{runner.num_epochs}) "
                msg = prefix + _format_metrics(metrics)
                print(msg)
            elif scope == "epoch":
                # @TODO: remove trick to save pure epoch-based metrics, like lr/momentum
                prefix = f"* Epoch ({runner.epoch_step}/{runner.num_epochs}) "
                msg = prefix + _format_metrics(metrics["_epoch_"])
                print(msg)


    runner = dl.SupervisedRunner(input_key="img", output_key="logits", target_key="targets", loss_key="loss")
    loaders = {"train": train_batch_gen, "valid": val_batch_gen}
    #model = BaseResNet(num_classes)
    model = DenseNet(Bottleneck, [6, 12, 24, 16], growth_rate=12, num_classes=num_classes).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

    # model training
    runner.train(
        model=model,
        criterion=criterion,
        optimizer=optimizer,
        loaders=loaders,
        loggers={"console": CustomLogger()},
        num_epochs=10,
        callbacks=[dl.AccuracyCallback(input_key="logits", target_key="targets", topk=(1, 3, 5)),],
        logdir="./logs_base",
        valid_loader="valid",
        valid_metric="loss", 
        minimize_valid_metric=True,
        verbose=True,
        load_best_on_end=True,
    )

import yaml
import pandas as pd
from sklearn.metrics import classification_report, precision_recall_fscore_support

"""#Testing"""

def load_ckpt(path, model, device=torch.device("cpu")):
    """
    Load saved checkpoint weights to model
    :param path: full path to checkpoint
    :param model: initialized model class nested from nn.Module()
    :param device: base torch device for validation
    :return: model with loaded 'state_dict'
    """
    assert os.path.isfile(path), FileNotFoundError(f"no file: {path}")

    ckpt = torch.load(path, map_location=device)
    #ckpt_dict = ckpt['model_state_dict']
    ckpt_dict = ckpt    
    model_dict = model.state_dict()
    ckpt_dict = {k: v for k, v in ckpt_dict.items() if k in model_dict}
    model_dict.update(ckpt_dict)
    model.load_state_dict(model_dict)
    return model

@torch.no_grad()
def validate_model(model, loader, device, val_ds):
    """
    Evaluate implemented model
    :param model: initialized model class nested from nn.Module() with loaded state dict
    :param loader batch data loader for evaluation set
    :param device: base torch device for validation
    :return: dict performance metrics
    """
    label_list = []
    pred_list = []
    model.train(False)
    model = model.to(device)

    for data_tensor, lbl_tensor in loader:
        lbl_values = lbl_tensor.cpu().view(-1).tolist()
        label_list.extend(lbl_values)
        logits = model(data_tensor.to(device))
        scores = F.softmax(logits.detach().cpu(), 1).numpy()
        pred_labels = np.argmax(scores, 1)
        pred_list.extend(pred_labels.ravel().tolist())

    labels = np.array(label_list)
    predicted = np.array(pred_list)
    metrics_pre_rec_f1 = classification_report(labels, predicted, target_names=val_ds.classes, output_dict=True)
    #metrics_pre_rec_f1 = precision_recall_fscore_support(label, predicted, labels=val_ds.classes)
    test_acc = accuracy_score(labels, predicted)
    #print(f"model accuracy: {acc:.4f}")
    #metric_dict = {"accuracy": acc}

    df = pd.DataFrame(metrics_pre_rec_f1).transpose()

    with open('metrics.yaml', 'w') as f:
        yaml.dump(metrics_pre_rec_f1, f)
        f.write('\n')
        yaml.dump({'test accuracy': test_acc}, f)
  
    return df

"""#Converting to ONNX"""

def to_onnx_export(model, data):
    output_onnx = 'model_convert.onnx'
    torch_out = torch.onnx.export(model, 
                                data, 
                                output_onnx, 
                                input_names=['input'], 
                                output_names=['output'], 
                                dynamic_axes={'input': {0: 'batch_size'}},
                                verbose=True)   
    return output_onnx

import re
import onnx
import onnxruntime as ort

if __name__ == "__main__":
    print("Using device: ", device)
    
    print("##############################")
    print("Training the model")
    print("??????????????????????????????????????????????????????")
    training()
    model = DenseNet(Bottleneck, [6, 12, 24, 16], growth_rate=12, num_classes=num_classes).to(device)
    cifar_model_summary(model, device)
    #################################
    #################################
    print("##############################")
    print("Testing the model")
    print("??????????????????????????????????????????????????????")
    ckpt_fp = 'logs_base/checkpoints/model.best.pth'
    mod = load_ckpt(ckpt_fp, model).eval()
    new_runner = validate_model(mod, loaders["valid"], device, val_ds)
    print(new_runner)
    #################################
    #################################
    print("Convert model to ONNX")
    print("??????????????????????????????????????????????????????")
    dummy_input = torch.randn(1, 3, 32, 32)
    model_in_onnx = to_onnx_export(mod.to(device), dummy_input.to(device))
    onnx_model = onnx.load("model_convert.onnx")
    onnx.checker.check_model(onnx_model)
    print(model_in_onnx)