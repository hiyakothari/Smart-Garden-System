# Wiring Diagram - Smart Garden System

## 📐 Component Layout

```
┌─────────────────────────────────────────────────────────┐
│                    ESP32 DevKit                         │
│                                                         │
│  3.3V ●────────────┐                        ● VIN      │
│                    │                        │           │
│  GND  ●────────────┼────────────────────────┼────●──┐  │
│                    │                        │      │   │
│  GPIO34 ●──────────┼────────────────┐       │      │   │
│                    │                │       │      │   │
│  GPIO5  ●──────────┼────────────────┼───────┼──┐   │   │
│                    │                │       │  │   │   │
└────────────────────┼────────────────┼───────┼──┼───┼───┘
                     │                │       │  │   │
                     │                │       │  │   │
         ┌───────────┴──────┐  ┌──────┴───────┴──┴───┴───┐
         │  Soil Moisture   │  │     Relay Module         │
         │     Sensor       │  │                          │
         │                  │  │  VCC  IN  GND  COM NO NC │
         │  VCC AOUT GND    │  │   ●   ●   ●    ●  ●  ●  │
         └───────────────────┘  └───────────────┬──┬──────┘
                                                 │  │
                                    ┌────────────┘  │
                                    │               │
                                    ▼               ▼
                            ┌─────────────────────────┐
                            │    Water Pump (5V DC)   │
                            │         + Red  - Black  │
                            └─────────────────────────┘
                                    ▲
                                    │
                            ┌───────┴─────────┐
                            │  Power Supply   │
                            │     5V 2A       │
                            └─────────────────┘
```

## 🔌 Detailed Connections

### ESP32 to Soil Moisture Sensor

| ESP32 Pin | Sensor Pin | Wire Color | Function |
|-----------|------------|------------|----------|
| 3.3V      | VCC        | Red        | Power    |
| GND       | GND        | Black      | Ground   |
| GPIO34    | AOUT       | Yellow     | Analog Signal |

**Notes:**
- Use capacitive sensor (not resistive) for longer life
- Sensor reads 0-4095 on ESP32 (12-bit ADC)
- Lower values = more moisture

### ESP32 to Relay Module

| ESP32 Pin | Relay Pin | Wire Color | Function |
|-----------|-----------|------------|----------|
| GPIO5     | IN        | Green      | Control Signal |
| GND       | GND       | Black      | Ground |
| 5V (ext)  | VCC       | Red        | Power (from external supply) |

**Important:** 
- Relay VCC should be powered from external 5V supply, NOT ESP32
- ESP32 can only provide limited current (~40mA per pin)
- Share common ground between ESP32 and relay

### Relay to Water Pump

| Relay Terminal | Connection | Notes |
|----------------|------------|-------|
| COM (Common)   | Power Supply + (5V) | Common connection |
| NO (Normally Open) | Pump + (Red) | When activated |
| NC (Normally Closed) | Not used | - |
| Pump - (Black) | Power Supply - (GND) | Complete circuit |

**Circuit:**
```
Power Supply (+5V) → Relay COM
Relay NO → Pump (+)
Pump (-) → Power Supply (GND)
```

### Power Supply Connections

**Option 1: USB Power (Testing)**
```
USB Power Adapter (5V 2A)
├── ESP32 VIN pin (via micro USB)
└── Relay VCC + Pump (via screw terminals)
```

**Option 2: Dedicated Power Supply (Production)**
```
5V 2A Power Supply
├── ESP32 VIN + Relay VCC
└── Pump power (through relay)
```

## 🎨 Color Coding Guide

| Color  | Purpose          |
|--------|------------------|
| Red    | Power (+5V/3.3V) |
| Black  | Ground (GND)     |
| Yellow | Analog Signals   |
| Green  | Digital Signals  |
| Blue   | Optional I2C/SPI |
| White  | Optional sensors |

## 📏 Physical Layout Recommendations

### Breadboard Layout (Testing)

```
ESP32 on right side of breadboard
Relay module on left side
Soil sensor connected via jumper wires (15-30cm)
Keep power supply off breadboard
```

### Permanent Installation

1. **Enclosure Selection:**
   - IP65 rated waterproof box
   - Dimensions: 150mm x 100mm x 70mm minimum
   - Cable glands for wire entry

2. **Component Mounting:**
   - ESP32: Mount on standoffs inside enclosure
   - Relay: Mount on DIN rail or standoffs
   - Power supply: External waterproof unit

3. **Cable Management:**
   - Soil sensor: 2-5m cable (extend if needed)
   - Pump power: 1-3m cable
   - Use cable glands for waterproofing

## 🔧 Multi-Zone Setup (3 Sensors)

### Pin Assignment

| Zone       | Sensor Pin | Pump Pin | Description |
|------------|------------|----------|-------------|
| Zone 1     | GPIO34     | GPIO5    | Vegetables  |
| Zone 2     | GPIO35     | GPIO18   | Flowers     |
| Zone 3     | GPIO36     | GPIO19   | Herbs       |

### Wiring Changes

```
ESP32 GPIO34 → Soil Sensor 1
ESP32 GPIO35 → Soil Sensor 2  
ESP32 GPIO36 → Soil Sensor 3

ESP32 GPIO5  → Relay 1 IN
ESP32 GPIO18 → Relay 2 IN
ESP32 GPIO19 → Relay 3 IN

Use 4-channel relay module
Each relay controls one pump
Share common 5V power supply
```

## ⚡ Power Consumption

| Component | Current Draw | Notes |
|-----------|--------------|-------|
| ESP32 (active) | 160-260mA | WiFi on |
| ESP32 (sleep) | 10μA | Deep sleep |
| Soil Sensor | 5-20mA | Per sensor |
| Relay | 15-20mA | Coil current |
| Pump | 100-300mA | Depends on model |

**Total Maximum:** ~600mA  
**Recommended Supply:** 2A (with headroom)

## 🛡️ Safety Precautions

### Electrical Safety
1. Use proper wire gauge (22-18 AWG)
2. Ensure all connections are tight
3. No exposed metal/conductors
4. Use heat shrink tubing on connections
5. Keep electronics away from water

### Waterproofing
1. Seal enclosure properly
2. Use cable glands for entries
3. Silicone sealant on joints
4. Test with water spray before deployment
5. Mount enclosure above ground level

### Grounding
1. Common ground for all components
2. No ground loops
3. Metal enclosure should be grounded

## 🧪 Testing Checklist

### Before Power On
- All connections match diagram
- No shorts between power/ground
- Proper polarity on all components
- Relay isolated from water
- Pump in water reservoir

### After Power On
- ESP32 boots (LED indicator)
- Soil sensor reads values (0-4095)
- Relay clicks when GPIO goes HIGH
- Pump turns on when relay activates
- No overheating components
- Serial monitor shows proper output

## 🔍 Troubleshooting

### Sensor Not Reading
- Check 3.3V power at sensor
- Verify GPIO34 connection
- Test with multimeter (should read 0-3.3V)

### Relay Not Switching
- Check GPIO5 voltage (should be 3.3V HIGH)
- Verify relay LED indicator
- Test relay manually with 5V

### Pump Not Running
- Check relay switching (click sound)
- Verify pump power supply (5V)
- Test pump directly with power supply
- Check current draw (may need bigger supply)

