// Render the Lite Store banner using the icon shared with the Full edition.
// Run from any directory with: swift tools/render_store_banner.swift

import AppKit
import Foundation

let description = URL(fileURLWithPath: #filePath)
    .deletingLastPathComponent()
    .deletingLastPathComponent()
    .appendingPathComponent("database_ultimate_backup_lite/static/description")

let width = 980
let height = 490
guard let bitmap = NSBitmapImageRep(
    bitmapDataPlanes: nil,
    pixelsWide: width,
    pixelsHigh: height,
    bitsPerSample: 8,
    samplesPerPixel: 4,
    hasAlpha: true,
    isPlanar: false,
    colorSpaceName: .deviceRGB,
    bytesPerRow: 0,
    bitsPerPixel: 0
), let context = NSGraphicsContext(bitmapImageRep: bitmap),
      let icon = NSImage(contentsOf: description.appendingPathComponent("icon_original.png"))
else {
    fatalError("Could not initialize banner graphics")
}

func color(_ hex: UInt32, alpha: CGFloat = 1) -> NSColor {
    NSColor(
        calibratedRed: CGFloat((hex >> 16) & 0xff) / 255,
        green: CGFloat((hex >> 8) & 0xff) / 255,
        blue: CGFloat(hex & 0xff) / 255,
        alpha: alpha
    )
}

func label(_ value: String, x: CGFloat, y: CGFloat, size: CGFloat,
           weight: NSFont.Weight, ink: NSColor) {
    let font = NSFont.systemFont(ofSize: size, weight: weight)
    (value as NSString).draw(
        at: NSPoint(x: x, y: y),
        withAttributes: [.font: font, .foregroundColor: ink]
    )
}

NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = context
context.imageInterpolation = .high

NSGradient(starting: color(0x0D1A32), ending: color(0x1E2B54))!
    .draw(in: NSRect(x: 0, y: 0, width: width, height: height), angle: 90)

color(0x6070DF, alpha: 0.11).setFill()
NSBezierPath(ovalIn: NSRect(x: 740, y: 160, width: 510, height: 510)).fill()
color(0x6070DF, alpha: 0.08).setFill()
NSBezierPath(ovalIn: NSRect(x: 805, y: -40, width: 315, height: 315)).fill()

let frame = NSBezierPath(roundedRect: NSRect(x: 29, y: 45, width: 922, height: 400),
                         xRadius: 40, yRadius: 40)
frame.lineWidth = 1.5
color(0x3A4977).setStroke()
frame.stroke()

icon.draw(in: NSRect(x: 88, y: 95, width: 300, height: 300),
          from: .zero, operation: .sourceOver, fraction: 1)

label("ODOO 20  /  DATABASE BACKUPS LITE", x: 430, y: 354,
      size: 19, weight: .bold, ink: color(0xB9C5FF))
label("Every backup,", x: 430, y: 258,
      size: 56, weight: .bold, ink: .white)
label("under control.", x: 430, y: 188,
      size: 56, weight: .bold, ink: .white)
label("Free  •  Local & SFTP  •  Verified", x: 430, y: 122,
      size: 23, weight: .regular, ink: color(0xD8DFFB))

NSGraphicsContext.restoreGraphicsState()
let output = description.appendingPathComponent("banner.png")
guard let data = bitmap.representation(using: .png, properties: [:]) else {
    fatalError("Could not encode banner")
}
try data.write(to: output)
print(output.path)
