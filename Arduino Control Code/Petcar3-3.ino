#define rightPin1 3
#define rightPin2 5

#define leftPin1 10
#define leftPin2 11

#define batteryPin A7
#define ADS_VREF_V 5.0f
#define DIVIDER_GAIN 2.0f

#define rx 0
#define tx 1

#define MAXSTRINGLENGTH 32

int leftPower = 0;
int rightPower = 0;

void parseCommand(char commandString[MAXSTRINGLENGTH]) {
  char *token;
  
  token = strtok(commandString, " ");
  //Serial.print("Token: ");
  //Serial.println(token);
  if(strcmp(token,"m") == 0) {
    //Serial.println("Motor call triggered");
    token = strtok(NULL, " "); // Get x value as cstring
    int xValue = atoi(token);

    token = strtok(NULL, " "); // Get y value as cstring
    int yValue = atoi(token);

    //Serial.print("Motor call, X: ");
    //Serial.print(xValue);
    //Serial.print(" Y: ");
    //Serial.println(yValue);

    convertToPower(xValue,yValue);

    //Serial.print("Motor powers: ");
    //Serial.print(leftPower);
    //Serial.print(", ");
    //Serial.println(rightPower);

    driveMotors(leftPower,rightPower);
  }
  else if(strcmp(token,"b") == 0) {
    // Query battery voltage
    float batVoltage = getBatteryVoltage();
    char sendStr[MAXSTRINGLENGTH] = "b ";
    char voltageStrBuffer[MAXSTRINGLENGTH-3];
    dtostrf(batVoltage, 0, 3, voltageStrBuffer);
    strcat(sendStr,voltageStrBuffer);
    Serial.println(sendStr);
  }

  /*while(token != NULL) {
    Serial.print("Token: ");
    Serial.println(token);
    token = strtok(NULL, " ");
  }*/
}

float getBatteryVoltage() {
  int analogValue = analogRead(batteryPin);
  
  #define inMin 0.0
  #define inMax 1023.0
  #define outMin 0.0
  #define outMax 5.0

  float rawVoltage = (analogValue-inMin) * (outMax-outMin) / (inMax-inMin) + outMin;
  return rawVoltage * 2;
}

void convertToPower(int x, int y) {
    leftPower = 255 * (y / 100.0);
    rightPower = 255 * (y / 100.0);

    if(y == 0) {
      leftPower = 255 * (x/100.0);
      rightPower = 255 * (-x/100.0);
    }
    else {
      if(x > 0) { // Leaning right
        rightPower *= (1 - (x / 100.0));
      }
      else if(x < 0) { // Leaning left
        leftPower *= (1 - (-x / 100.0));
      } 
    }
}

void driveMotors(int leftMotor, int rightMotor) {
  if(leftMotor < 0)
  {
    // Write left pin 1 to ground and left pin 2 to pwm
    digitalWrite(leftPin1, LOW);
    analogWrite(leftPin2, -leftMotor);
  }
  else if(leftMotor > 0)
  {
    // Write left pin 1 to pwm and left pin 2 to ground
    analogWrite(leftPin1, leftMotor);
    digitalWrite(leftPin2, LOW);
  }
  else
  {
    digitalWrite(leftPin2, LOW);
    digitalWrite(leftPin1, LOW);
  }

  if(rightMotor < 0) {
    // Write right pin 1 to ground and right pin 2 to pwm
    digitalWrite(rightPin1, LOW);
    analogWrite(rightPin2, -rightMotor);
  } else if(rightMotor > 0) {
    // Write right pin 1 to pwm and right pin 2 to ground
    analogWrite(rightPin1, rightMotor);
    digitalWrite(rightPin2, LOW);
  } else {
    digitalWrite(rightPin1, LOW);
    digitalWrite(rightPin2, LOW);
  }
}

void setup() {
  // put your setup code here, to run once:
  Serial.begin(9600);

  // Motor Pins
  pinMode(rightPin1, OUTPUT);
  pinMode(rightPin2, OUTPUT);
  pinMode(leftPin1, OUTPUT);
  pinMode(leftPin2, OUTPUT);

  // UART Pins
  pinMode(rx, INPUT);
  pinMode(tx, OUTPUT);
}

char incomingData[MAXSTRINGLENGTH];
int dataIndex = 0;
bool stringHandled = true;

void loop() {
  // put your main code here, to run repeatedly:

  while(Serial.available() > 0 && dataIndex < MAXSTRINGLENGTH-1) {
    char receivedChar = Serial.read(); // Read the incoming character

    // Check for the newline character, indicating end of data
    if (receivedChar == '\n') {
      incomingData[dataIndex] = '\0'; // Null-terminate the string
      //Serial.println(incomingData);    // Print the string
      dataIndex = 0;                   // Reset the index for the next string
      stringHandled = false;
    } else {
      // Add the character to the array and increment the index
      incomingData[dataIndex] = receivedChar;
      dataIndex++;
    }
  }

  if(!stringHandled) {
    //Serial.print("Recieved: ");
    //Serial.println(incomingData);    // Print the string

    parseCommand(incomingData);

    stringHandled = true;
  }
}
