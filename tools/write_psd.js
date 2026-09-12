"use strict";

const fs = require("node:fs");
const path = require("node:path");

if (process.argv.length !== 5) {
  throw new Error("usage: node write_psd.js <payload.json> <output.psd> <rig-summary.json>");
}

const payloadPath = path.resolve(process.argv[2]);
const outputPath = path.resolve(process.argv[3]);
const summaryPath = path.resolve(process.argv[4]);
const payload = JSON.parse(fs.readFileSync(payloadPath, "utf8"));
const vendorRoot = path.resolve(__dirname, "..", "vendor", "Anime2.5DRig");
const ag = require(path.join(vendorRoot, "lib", "ag-psd.min.js"));
const Rigger = require(path.join(vendorRoot, "lib", "rigger.js"));
const GenericParts = require(path.join(vendorRoot, "lib", "genericparts.js"));

ag.initializeCanvas(undefined, (width, height) => ({
  width,
  height,
  data: new Uint8ClampedArray(width * height * 4),
}));

function imageData(record) {
  const bytes = fs.readFileSync(path.resolve(path.dirname(payloadPath), record.raw));
  if (bytes.length !== record.width * record.height * 4) {
    throw new Error(`invalid RGBA byte count for ${record.raw}`);
  }
  return {
    width: record.width,
    height: record.height,
    data: new Uint8ClampedArray(bytes),
  };
}

const psd = {
  width: payload.width,
  height: payload.height,
  imageData: imageData(payload.composite),
  children: payload.layers.map((layer) => ({
    name: layer.name,
    left: layer.left,
    top: layer.top,
    right: layer.left + layer.width,
    bottom: layer.top + layer.height,
    blendMode: "normal",
    opacity: 1,
    imageData: imageData(layer),
  })),
};

const encoded = ag.writePsd(psd, { generateThumbnail: false });
fs.writeFileSync(outputPath, Buffer.from(encoded));

const rigOptions = payload.allowGeneric === false ? {} : {
  generic: {
    eyeL: GenericParts.get("eyeL"),
    eyeR: GenericParts.get("eyeR"),
    mouth: GenericParts.get("mouth"),
  },
};
const rig = Rigger.buildRig(psd, rigOptions);

const synthetic = [];
for (const part of rig.layers.filter((item) => item.synthetic)) {
  const rawName = `synthetic_${part.name.replace(/[^a-z0-9_-]+/gi, "_")}.rgba`;
  fs.writeFileSync(path.join(path.dirname(summaryPath), rawName), Buffer.from(part.img.data));
  synthetic.push({
    name: part.name,
    raw: rawName,
    left: part.x,
    top: part.y,
    width: part.w,
    height: part.h,
    side: part.side,
    fade: part.fade,
  });
}

const summary = {
  canvas: rig.canvas,
  anchors: rig.anchors,
  warnings: rig.warnings,
  synth: rig.synth,
  layerCount: rig.layers.length,
  synthetic,
};
fs.writeFileSync(summaryPath, JSON.stringify(summary, null, 2), "utf8");
