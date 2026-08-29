#!/usr/bin/env node
const fs = require("fs");
const path = require("path");

function loadArchive(archivePath) {
  const fd = fs.openSync(archivePath, "r");
  const hdr = Buffer.alloc(16);
  fs.readSync(fd, hdr, 0, hdr.length, 0);
  const pickleSize = hdr.readUInt32LE(4);
  const jsonSize = hdr.readUInt32LE(12);
  const json = Buffer.alloc(jsonSize);
  fs.readSync(fd, json, 0, jsonSize, 16);
  return { fd, header: JSON.parse(json.toString("utf8")), base: 8 + pickleSize };
}

function findNode(header, filePath) {
  const parts = filePath.split("/").filter(Boolean);
  let node = header;
  for (const part of parts) {
    if (!node.files || !node.files[part]) return null;
    node = node.files[part];
  }
  return node;
}

function listFiles(node, prefix = "") {
  if (!node.files) {
    console.log(prefix);
    return;
  }
  for (const [name, child] of Object.entries(node.files)) {
    listFiles(child, prefix ? `${prefix}/${name}` : name);
  }
}

const [archivePath, command, filePath] = process.argv.slice(2);
if (!archivePath || !command) {
  console.error("usage: asar_extract.js <app.asar> list|cat|extract [file] [out]");
  process.exit(2);
}

const archive = loadArchive(archivePath);
if (command === "list") {
  listFiles(archive.header);
  process.exit(0);
}

const node = findNode(archive.header, filePath || "");
if (!node || node.files || node.offset == null || node.size == null) {
  console.error(`file not found: ${filePath}`);
  process.exit(1);
}

const offset = archive.base + Number(node.offset);
const data = Buffer.alloc(node.size);
fs.readSync(archive.fd, data, 0, node.size, offset);

if (command === "cat") {
  process.stdout.write(data);
} else if (command === "extract") {
  const out = process.argv[5] || path.basename(filePath);
  fs.mkdirSync(path.dirname(out), { recursive: true });
  fs.writeFileSync(out, data);
} else {
  console.error(`unknown command: ${command}`);
  process.exit(2);
}
