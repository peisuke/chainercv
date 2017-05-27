from __future__ import division

import numpy as np
import six

from chainer import cuda


def _to_cpu(arrays, xp):
    if isinstance(arrays, xp.ndarray):
        out_arrays = cuda.to_cpu(arrays)
    else:
        out_arrays = []
        for i in six.moves.range(len(arrays)):
            out_arrays.append(cuda.to_cpu(arrays[i]))
    return out_arrays


def _fast_hist(pred_label, gt_label, n_class):
    # Construct histogram for label evaluation.

    mask = (gt_label >= 0) & (gt_label < n_class)
    # an array of shape (n_class, n_class)
    hist = np.bincount(
        n_class * gt_label[mask].astype(int) +
        pred_label[mask], minlength=n_class**2).reshape(n_class, n_class)
    return hist


def eval_semantic_segmentation(pred_label, gt_label, n_class):
    """Evaluate results of semantic segmentation.

    This function measures four metrics: pixel accuracy,
    mean pixel accuracy, mean intersection over union and
    frequency weighted intersection over union.

    The definition of these metrics are as follows, where
    :math:`N_{ij}` is the amount of pixels of class :math:`i`
    inferred to belong to :math:`j` and there is :math:`k` classes.

    * Pixel Accuracy (PA)
        :math:`PA = \\frac
        {\\sum_{i=1}^k N_{ii}}
        {\\sum_{i=1}^k \\sum_{j=1}^k N_{ij}}`
    * Mean Pixel Accuracy (MPA)
        :math:`MPA = \\frac{1}{k}
        \\sum_{i=1}^k
        \\frac{N_{ii}}{\\sum_{j=1}^k N_{ij}}`
    * Mean Intersection over Union (MIoU)
        :math:`MIoU = \\frac{1}{k}
        \\sum_{i=1}^k
        \\frac{N_{ii}}{\\sum_{j=1}^k N_{ij} + \\sum_{j=1}^k N_{ji} - N_{ii}}`
    * Frequency Weighted Intersection over Union (FWIoU)
        :math:`FWIoU = \\frac{1}{\\sum_{i=1}^k \\sum_{j=1}^k N_{ij}}
        \\sum_{i=1}^k \\frac{\\sum_{j=1}^k N_{ij}N_{ii}}
        {\\sum_{j=1}^k N_{ij} + \\sum_{j=1}^k N_{ji} - N_{ii}}`

    The more detailed descriptions on the above metrics can be found at a
    review on semantic segmentation [#]_.

    Types of :obj:`pred_label` and :obj:`gt_label` need to be same.
    The outputs are same type as the inputs.

    .. [#] Alberto Garcia-Garcia, Sergio Orts-Escolano, Sergiu Oprea, \
    Victor Villena-Martinez, Jose Garcia-Rodriguez. \
    `A Review on Deep Learning Techniques Applied to Semantic Segmentation \
    <https://arxiv.org/abs/1704.06857>`_. arXiv 2017.

    Args:
        pred_label (iterable of arrays): A collection of predicted labels.
            This is an interable of labels or a single label.
            An array of label has shape :math:`H, W)`.
            :math:`H` and :math:`W`
            are height and width of the images. We assume that there are
            :math:`N` labels.
        gt_label (iterable of arrays): A collection of the ground truth labels.
            Its organized similarly to :obj:`pred_label`. A pixel with value
            "-1" will be ignored during evaluation.
            We assume that there are :math:`N` labels.
        n_class (int): Number of classes.

    Returns:
        (array, array, array, array):
        A tuple of pixel accuracy, mean pixel accuracy, MIoU and FWIoU.
        These arrays have shape :math:`(N,)`, where :math:`N` is
        the number of images in the input.

    """
    # Evaluation code is based on 
    # https://github.com/shelhamer/fcn.berkeleyvision.org/blob/master/
    # score.py#L37
    xp = cuda.get_array_module(pred_label[0], gt_label[0])
    if isinstance(pred_label, xp.ndarray) and pred_label.ndim == 2:
        pred_label = [pred_label]
    if isinstance(gt_label, xp.ndarray) and gt_label.ndim == 2:
        gt_label = [gt_label]
    pred_label = _to_cpu(pred_label, xp)
    gt_label = _to_cpu(gt_label, xp)
    N = len(pred_label)

    if len(pred_label) != len(gt_label):
        raise ValueError('Number of the predicted labels and the'
                         'ground truth labels are different')
    for i in six.moves.range(N):
        if pred_label[i].shape != gt_label[i].shape:
            raise ValueError('Shape of a prediction and'
                             'the ground truth should match')

    acc = np.zeros((N,))
    acc_cls = np.zeros((N,))
    mean_iou = np.zeros((N,))
    fwavacc = np.zeros((N,))
    for i in six.moves.range(N):
        hist = _fast_hist(
            pred_label[i].flatten(), gt_label[i].flatten(), n_class)
        acc[i] = np.diag(hist).sum() / hist.sum()
        with np.errstate(divide='ignore', invalid='ignore'):
            acc_cls_i = np.diag(hist) / hist.sum(axis=1)
            acc_cls[i] = np.nanmean(acc_cls_i)
        iou_denominator = (hist.sum(axis=1) + hist.sum(axis=0) - np.diag(hist))
        iou = np.diag(hist) / iou_denominator
        mean_iou[i] = np.nanmean(iou)
        freq = hist.sum(axis=1) / hist.sum()
        fwavacc[i] = (freq[freq > 0] * iou[freq > 0]).sum()

    return (xp.asarray(acc), xp.asarray(acc_cls),
            xp.asarray(mean_iou), xp.asarray(fwavacc))
