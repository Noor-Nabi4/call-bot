const path = require("path");
const fs = require("fs");
const sharp = require(path.join(__dirname, "..", "web", "node_modules", "sharp"));

const branding = path.join(__dirname, "..", "branding");

async function main() {
  const iconSvg = fs.readFileSync(path.join(branding, "icon.svg"));
  const faviconSvg = fs.readFileSync(path.join(branding, "favicon.svg"));

  await sharp(iconSvg, { density: 300 })
    .resize(512, 512)
    .png()
    .toFile(path.join(branding, "icon.png"));
  console.log("icon.png");

  const mark = await sharp(faviconSvg).resize(160, 160).png().toBuffer();
  const caption = Buffer.from(
    `<svg xmlns="http://www.w3.org/2000/svg" width="800" height="200">
      <text x="0" y="70" fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif" font-size="56" font-weight="700">Call &amp; Flow</text>
      <text x="0" y="130" fill="#94A3B8" font-family="Arial, Helvetica, sans-serif" font-size="26">AI Voice Platform for Service Businesses and Call Centers</text>
      <text x="0" y="175" fill="#14B8A6" font-family="Arial, Helvetica, sans-serif" font-size="22">Build AI Voice Agents for Any Business.</text>
    </svg>`,
  );

  await sharp({
    create: {
      width: 1200,
      height: 630,
      channels: 3,
      background: { r: 15, g: 23, b: 42 },
    },
  })
    .composite([
      { input: mark, top: 180, left: 120 },
      { input: caption, top: 200, left: 320 },
    ])
    .png()
    .toFile(path.join(branding, "social-preview.png"));
  console.log("social-preview.png");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
