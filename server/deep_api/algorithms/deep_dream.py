"""
Deep Dream Algorithm.
"""

import torch
import torchvision
import logging
from torchvision import transforms as T
from PIL import Image, ImageFilter

logger = logging.getLogger('DEEP_API')

MEAN = [0.485, 0.456, 0.406]
STD = [0.229, 0.224, 0.225]
IMEAN = [-0.485/0.229, -0.456/0.224, -0.406/0.225]
ISTD = [1/0.229, 1/0.224, 1/0.225]
SIZE = 512


def preprocess(image):
    """
    Preprocesses the image to be fed to the Deep Model Algorithm.
    Resizes, normalizes the image and performs Pytorch Tensor Conversion.
    """
    transforms = T.Compose([
        T.Resize((SIZE, SIZE)),
        T.ToTensor(),
        T.Normalize(mean=MEAN, std=STD)
    ])
    return transforms(image).unsqueeze(0).requires_grad_(True)


def postprocess(tensor):
    """
    Processes the output for the Deep Dream Algorithm.
    """
    transforms = T.Compose([
        T.Normalize(IMEAN, ISTD),
        T.ToPILImage()
    ])
    return transforms(tensor)


def clip(image):
    """
    Set the image pixel values between 0 and 1.
    """
    for c, (mean, std) in enumerate(zip(MEAN, STD)):
        image[0, c] = torch.clamp(image[0, c], -mean/std, (1 - mean)/std)
    return image


def scaled(image, factor):
    """
    Resize the image to a given scale factor.
    """
    width = int(image.width * factor)
    height = int(image.height * factor)
    return image.resize((width, height))


class DeepGoogLeNet(torchvision.models.GoogLeNet):
    """
    GoogLeNet Extension for Deep Dream.
    Params:
        - loi: layers of interest: names of the layers that will be saved
                with hooks to get their outputs.
        - weights_path: pretrained weights path
        - **kwargs: same args as in torchvision.models.GoogLeNet
    """
    features = []
    hooks = []

    def __init__(self, loi, weights_path, **kwargs):
        super(DeepGoogLeNet, self).__init__(**kwargs)

        # load pretrained weights
        weights = torch.load(weights_path)
        self.load_state_dict(weights)

        # prepare hooks to save features
        for layer_name in loi:
            layer = dict(self.named_children())[layer_name]
            layer_hook = layer.register_forward_hook(self.feature_hook)
            self.hooks.append(layer_hook)

    def feature_hook(self, module, _in, _out):
        self.features.append(_out)

    def remove(self):
        [hook.remove() for hook in self.hooks]

    def forward(self, x):
        self.features = []
        return super(DeepGoogLeNet, self).forward(x)


class DeepDream:
    """
    Deep Dream Algorithm.
    """

    def __init__(self, loi, weights_path):
        self.model = DeepGoogLeNet(loi=loi, weights_path=weights_path)
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.device = torch.device(device)
        logger.info('Deep Dream Class Initialized succesfully')

    def deep_dream_loss(self, model, target):
        """
        Deep Dream Loss:
        Uses the model features (declared when setting the model hooks)
        and uses the sum of the mean values of these features as loss.
        """
        # run the image through the net
        _ = model(target)

        # get the loss
        losses = [torch.mean(feat) for feat in model.features]
        loss = torch.stack(losses, axis=0).sum()
        return loss

    def dream_inception(self,
                        image,
                        epochs,
                        learning_rate,
                        learning_weight):
        """
        Deep Dream Inception.
        Passes the given image through the model and uses the
        Gradient Ascent Method to update the image.
        """
        target = preprocess(image).to(self.device)
        logger.debug(f'Dream inception target with shape: {target.shape}')
        for _ in range(epochs):
            # reset gradient
            if target.grad is not None:
                target.grad.zero_()

            # loss backward
            loss = self.deep_dream_loss(self.model, target)
            loss.backward(retain_graph=True)

            # gradient ascent step (standarizing the gradient)
            grad = target.grad.data / (torch.std(target.grad.data) + 1e-8)
            learning_rate = learning_rate / learning_weight
            target.data = target.data + grad * learning_rate

            # clip pixel values
            target.data = clip(target.data)
        return target

    def create_inceptions(self,
                          image,
                          n_inceptions,
                          scale_factor,
                          blur_radius):
        """
        Creates the deep dream inceptions given the original image.
        In order to get the best result for the Deep Dream Algorithm,
        we need to create different samples, using the original image
        downscaled and blured.
        """
        inceptions = [image]
        for i in range(n_inceptions - 1):
            inception = inceptions[-1]
            inception = inception.filter(ImageFilter.GaussianBlur(blur_radius))
            inception = scaled(inception, scale_factor)
            inceptions.append(inception)
        return inceptions

    def __call__(self,
                 image,
                 epochs=10,
                 learning_rate=1,
                 loi=['Mixed_5b', 'Mixed_6b'],
                 n_inceptions=5,
                 scale_factor=0.7,
                 blend_factor=0.3,
                 blur_radius=60):
        """
        This is the main call to perform the Deep Dream algorithm,
        it creates the inceptions (original image downscaled and blured)
        and optimizes each of these running them through the model.
        Each inception is also blended with the following inception.
        """

        # create inceptions
        inceptions = self.create_inceptions(image,
                                            n_inceptions,
                                            scale_factor,
                                            blur_radius)
        logger.debug(f'Created {n_inceptions} inceptions')

        # run a step for each of these
        dream = None
        for w, inception in enumerate(inceptions[::-1]):
            if dream is not None:
                # upsample and blend last inception
                dream = dream.resize(inception.size)
                scale = Image.blend(inception, dream, blend_factor)

            # run the step
            logger.debug(f'Running inception on sample {w}'
                         f' with size: {inception.size}')
            learning_weight = w + 1
            dream = self.dream_inception(inception,
                                         epochs,
                                         learning_rate,
                                         learning_weight)

            # re convert to PIL and save for the next it
            dream = dream.cpu().clone().detach().squeeze(0)
            dream = postprocess(dream)

        return dream