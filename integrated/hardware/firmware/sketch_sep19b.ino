
#include <Wire.h>
#include <math.h>

// =====================================
// CONTEXTSWITCH IMU FIRMWARE
// Raspberry Pi Pico H + MPU9250/6500
// =====================================

#define SDA_PIN 4
#define SCL_PIN 5

#define SAMPLE_RATE_HZ 50
#define SAMPLE_INTERVAL_US (1000000UL / SAMPLE_RATE_HZ)

#define GYRO_CALIBRATION_SAMPLES 300

uint8_t imuAddress = 0x68;

float gyroBiasX = 0.0f;
float gyroBiasY = 0.0f;
float gyroBiasZ = 0.0f;

bool imuReady = false;
bool calibrated = false;

unsigned long lastSampleUs = 0;
unsigned long packetCount = 0;


// =====================================
// I2C FUNCTIONS
// =====================================

bool writeRegister(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(imuAddress);
  Wire.write(reg);
  Wire.write(value);

  return Wire.endTransmission() == 0;
}

bool readRegisters(
  uint8_t reg,
  uint8_t *buffer,
  uint8_t length
) {
  Wire.beginTransmission(imuAddress);
  Wire.write(reg);

  if (Wire.endTransmission(false) != 0) {
    return false;
  }

  int received = Wire.requestFrom(
    (int)imuAddress,
    (int)length
  );

  if (received != length) {
    return false;
  }

  for (uint8_t i = 0; i < length; i++) {
    buffer[i] = Wire.read();
  }

  return true;
}

int16_t toInt16(uint8_t high, uint8_t low) {
  return (int16_t)(
    ((uint16_t)high << 8) | low
  );
}


// =====================================
// IMU DETECTION
// =====================================

bool detectIMU() {
  uint8_t addresses[] = {0x68, 0x69};

  for (uint8_t i = 0; i < 2; i++) {
    imuAddress = addresses[i];

    uint8_t whoami = 0;

    if (!readRegisters(0x75, &whoami, 1)) {
      continue;
    }

    // MPU9250 = 0x71 or 0x73
    // MPU6500 = 0x70
    if (
      whoami == 0x71 ||
      whoami == 0x73 ||
      whoami == 0x70
    ) {
      Serial.print("# IMU_FOUND,address=0x");
      Serial.print(imuAddress, HEX);
      Serial.print(",whoami=0x");
      Serial.println(whoami, HEX);

      return true;
    }
  }

  return false;
}


// =====================================
// SENSOR INITIALIZATION
// =====================================

bool initializeIMU() {
  // Wake sensor, select PLL clock
  if (!writeRegister(0x6B, 0x01)) {
    return false;
  }

  delay(100);

  // Enable all accelerometer/gyro axes
  if (!writeRegister(0x6C, 0x00)) {
    return false;
  }

  // Gyro DLPF configuration
  if (!writeRegister(0x1A, 0x03)) {
    return false;
  }

  // Gyroscope +/- 250 deg/s
  if (!writeRegister(0x1B, 0x00)) {
    return false;
  }

  // Accelerometer +/- 2g
  if (!writeRegister(0x1C, 0x00)) {
    return false;
  }

  // Accelerometer DLPF
  if (!writeRegister(0x1D, 0x03)) {
    return false;
  }

  // Sample rate divider (1 kHz / 20 = 50 Hz)
  if (!writeRegister(0x19, 19)) {
    return false;
  }

  delay(100);

  return true;
}


// =====================================
// SENSOR READING
// =====================================

bool readIMU(
  float &ax,
  float &ay,
  float &az,
  float &gx,
  float &gy,
  float &gz
) {
  uint8_t data[14];

  if (!readRegisters(0x3B, data, 14)) {
    return false;
  }

  int16_t rawAx = toInt16(data[0], data[1]);
  int16_t rawAy = toInt16(data[2], data[3]);
  int16_t rawAz = toInt16(data[4], data[5]);

  int16_t rawGx = toInt16(data[8], data[9]);
  int16_t rawGy = toInt16(data[10], data[11]);
  int16_t rawGz = toInt16(data[12], data[13]);

  ax = rawAx / 16384.0f;
  ay = rawAy / 16384.0f;
  az = rawAz / 16384.0f;

  gx = rawGx / 131.0f;
  gy = rawGy / 131.0f;
  gz = rawGz / 131.0f;

  return true;
}


// =====================================
// GYROSCOPE CALIBRATION
// =====================================

bool calibrateGyro() {
  Serial.println("# CALIBRATION_START");
  Serial.println("# KEEP_SENSOR_STILL");

  float sumX = 0.0f;
  float sumY = 0.0f;
  float sumZ = 0.0f;

  float ax, ay, az;
  float gx, gy, gz;

  for (
    int i = 0;
    i < GYRO_CALIBRATION_SAMPLES;
    i++
  ) {
    if (!readIMU(
      ax, ay, az,
      gx, gy, gz
    )) {
      Serial.println("# CALIBRATION_FAILED");
      calibrated = false;
      return false;
    }

    sumX += gx;
    sumY += gy;
    sumZ += gz;

    delay(20);
  }

  gyroBiasX = sumX / GYRO_CALIBRATION_SAMPLES;
  gyroBiasY = sumY / GYRO_CALIBRATION_SAMPLES;
  gyroBiasZ = sumZ / GYRO_CALIBRATION_SAMPLES;

  calibrated = true;

  Serial.print("# GYRO_BIAS,");
  Serial.print(gyroBiasX, 4);
  Serial.print(",");
  Serial.print(gyroBiasY, 4);
  Serial.print(",");
  Serial.println(gyroBiasZ, 4);

  Serial.println("# CALIBRATION_DONE");

  return true;
}


// =====================================
// SERIAL COMMANDS
// =====================================

void handleCommands() {
  while (Serial.available()) {
    char command = Serial.read();

    if (command == 'c' || command == 'C') {
      calibrateGyro();
      lastSampleUs = micros();
    }

    else if (command == 's' || command == 'S') {
      Serial.print("# STATUS,ready=");
      Serial.print(imuReady ? 1 : 0);
      Serial.print(",calibrated=");
      Serial.print(calibrated ? 1 : 0);
      Serial.print(",packets=");
      Serial.println(packetCount);
    }
  }
}


// =====================================
// SETUP
// =====================================

void setup() {
  Serial.begin(115200);

  delay(1500);

  Wire.setSDA(SDA_PIN);
  Wire.setSCL(SCL_PIN);
  Wire.begin();
  Wire.setClock(400000);

  Serial.println("# CONTEXTSWITCH_IMU_V1");

  imuReady = detectIMU();

  if (!imuReady) {
    Serial.println("# ERROR_IMU_NOT_FOUND");
    return;
  }

  if (!initializeIMU()) {
    imuReady = false;
    Serial.println("# ERROR_IMU_INIT");
    return;
  }

  calibrateGyro();

  Serial.println(
    "# CSV: timestamp_ms,ax,ay,az,gx,gy,gz"
  );

  lastSampleUs = micros();
}


// =====================================
// MAIN LOOP
// =====================================

void loop() {
  if (!imuReady) {
    delay(1000);
    return;
  }

  handleCommands();

  unsigned long now = micros();

  if (
    (unsigned long)(now - lastSampleUs)
    < SAMPLE_INTERVAL_US
  ) {
    return;
  }

  lastSampleUs += SAMPLE_INTERVAL_US;

  // Prevent a backlog after pauses/calibration
  if (
    (unsigned long)(micros() - lastSampleUs)
    >= SAMPLE_INTERVAL_US
  ) {
    lastSampleUs = micros();
  }

  float ax, ay, az;
  float gx, gy, gz;

  if (!readIMU(
    ax, ay, az,
    gx, gy, gz
  )) {
    Serial.println("# ERROR_IMU_READ");
    return;
  }

  // Apply gyro bias correction
  gx -= gyroBiasX;
  gy -= gyroBiasY;
  gz -= gyroBiasZ;

  // CSV timestamp and sensor values
  Serial.print(millis());
  Serial.print(",");

  Serial.print(ax, 4);
  Serial.print(",");
  Serial.print(ay, 4);
  Serial.print(",");
  Serial.print(az, 4);
  Serial.print(",");

  Serial.print(gx, 4);
  Serial.print(",");
  Serial.print(gy, 4);
  Serial.print(",");
  Serial.println(gz, 4);

  packetCount++;
}
