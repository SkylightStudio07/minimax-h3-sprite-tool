"""Motion-compensated alpha stabilisation for per-frame sprite cutouts.

Each frame's matte is computed independently, so the silhouette boils from frame
to frame. Neighbouring alphas are aligned to the current frame with optical flow
and combined with a weighted median, inside a narrow band around the contour.
Interior pixels, drawn colours and the rest of the frame are never altered.
Pixels whose source colour disagrees with a neighbour (fast motion, muzzle
flashes, occlusion) lose that neighbour's vote, so effects keep their own matte.
"""
import cv2
import numpy as np
from scipy import ndimage

REVISION = 'temporal-matte-v1'


def _gray(rgb):
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)


def _band(alpha, width):
    solid = alpha > 127
    inside = ndimage.distance_transform_edt(solid)
    outside = ndimage.distance_transform_edt(~solid)
    return (solid & (inside <= width)) | (~solid & (outside <= width))


def _neighbours(index, count, radius, loop):
    for offset in range(-radius, radius + 1):
        other = index + offset
        if offset == 0:
            continue
        if loop:
            yield other % count
        elif 0 <= other < count:
            yield other


def _weighted_median(values, weights):
    order = np.argsort(values, axis=1)
    rows = np.arange(values.shape[0])[:, None]
    ordered = values[rows, order]
    cumulative = np.cumsum(weights[rows, order], axis=1)
    picks = np.argmax(cumulative >= cumulative[:, -1:] * .5, axis=1)
    return ordered[rows[:, 0], picks]


def stabilize(raw_frames, cutouts, radius=2, band=4, sigma=12.0, loop=False):
    """Return stabilised RGBA arrays. Inputs are equal-length uint8 HxWx3 / HxWx4 lists."""
    if len(raw_frames) != len(cutouts):
        raise ValueError('원본 프레임과 누끼 프레임 수가 다릅니다.')
    if radius < 1 or band < 1:
        raise ValueError('radius와 band는 1 이상이어야 합니다.')
    count = len(raw_frames)
    grays = [_gray(frame) for frame in raw_frames]
    flow_engine = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    height, width = grays[0].shape
    grid_x, grid_y = np.meshgrid(np.arange(width, dtype=np.float32), np.arange(height, dtype=np.float32))
    output = []
    for index in range(count):
        current = cutouts[index].copy()
        alpha = current[:, :, 3]
        mask = _band(alpha, band)
        ys, xs = np.nonzero(mask)
        others = list(_neighbours(index, count, radius, loop))
        if not len(ys) or not others:
            output.append(current)
            continue
        votes = [alpha[ys, xs].astype(np.float32)]
        weights = [np.ones(len(ys), np.float32)]
        colours, colour_weights = [], []
        reference = raw_frames[index].astype(np.float32)
        for other in others:
            flow = flow_engine.calc(grays[index], grays[other], None)
            map_x, map_y = grid_x + flow[:, :, 0], grid_y + flow[:, :, 1]
            warped_raw = cv2.remap(raw_frames[other], map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE).astype(np.float32)
            warped = cv2.remap(cutouts[other], map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE).astype(np.float32)
            error = np.sum((reference[ys, xs] - warped_raw[ys, xs]) ** 2, axis=1) / 3
            weight = np.exp(-error / (2 * sigma * sigma))
            votes.append(warped[ys, xs, 3])
            weights.append(weight)
            colours.append(warped[ys, xs, :3])
            colour_weights.append(weight * warped[ys, xs, 3])
        result = _weighted_median(np.stack(votes, axis=1), np.stack(weights, axis=1))
        new_alpha = np.rint(result).astype(np.uint8)
        # Pixels that gain opacity have no colour of their own; borrow the aligned neighbours'.
        empty = (alpha[ys, xs] < 10) & (new_alpha >= 10)
        if empty.any():
            stacked = np.stack([c[empty] for c in colours], axis=1)
            vote = np.stack([w[empty] for w in colour_weights], axis=1)[:, :, None]
            filled = np.sum(stacked * vote, axis=1) / np.maximum(np.sum(vote, axis=1), 1e-3)
            py, px = ys[empty], xs[empty]
            current[py, px, :3] = np.rint(filled).astype(np.uint8)
        current[ys, xs, 3] = new_alpha
        current[current[:, :, 3] == 0] = 0
        output.append(current)
    return output


def static_flicker(raw_frames, cutouts, band=4, threshold=6.0):
    """Mean alpha change (0-255) on contour pixels whose source colour did not change."""
    total, pixels = 0.0, 0
    for index in range(len(raw_frames) - 1):
        difference = np.max(np.abs(raw_frames[index + 1].astype(np.float32) - raw_frames[index].astype(np.float32)), axis=2)
        alpha_a = cutouts[index][:, :, 3].astype(np.float32)
        alpha_b = cutouts[index + 1][:, :, 3].astype(np.float32)
        mask = _band(cutouts[index][:, :, 3], band) & (difference < threshold)
        total += float(np.abs(alpha_a - alpha_b)[mask].sum())
        pixels += int(mask.sum())
    return total / max(pixels, 1)
