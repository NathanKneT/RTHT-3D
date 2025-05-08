import cv2
import mediapipe as mp
import numpy as np
import socket
import time

# Initialize MediaPipe Hands
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

# Initialize UDP socket for communication with Blender
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
blender_address = ('localhost', 5006)  # Make sure this matches Blender's PORT

# Initialize webcam
cap = cv2.VideoCapture(0)
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

# Previous hand position for calculating movement
prev_index_tip = None
last_gesture = None
last_gesture_hand2 = None

def detect_gestures(hand_landmarks):
    """Detect gestures based on hand landmarks"""
    # Extract key points
    thumb_tip = np.array([hand_landmarks.landmark[mp_hands.HandLandmark.THUMB_TIP].x, 
                         hand_landmarks.landmark[mp_hands.HandLandmark.THUMB_TIP].y])
    index_tip = np.array([hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP].x, 
                         hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP].y])
    middle_tip = np.array([hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_TIP].x, 
                          hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_TIP].y])
    ring_tip = np.array([hand_landmarks.landmark[mp_hands.HandLandmark.RING_FINGER_TIP].x, 
                        hand_landmarks.landmark[mp_hands.HandLandmark.RING_FINGER_TIP].y])
    pinky_tip = np.array([hand_landmarks.landmark[mp_hands.HandLandmark.PINKY_TIP].x, 
                         hand_landmarks.landmark[mp_hands.HandLandmark.PINKY_TIP].y])
    
    # Get PIP joints (second knuckle)
    index_pip = np.array([hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_PIP].x, 
                         hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_PIP].y])
    middle_pip = np.array([hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_PIP].x, 
                          hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_PIP].y])
    ring_pip = np.array([hand_landmarks.landmark[mp_hands.HandLandmark.RING_FINGER_PIP].x, 
                        hand_landmarks.landmark[mp_hands.HandLandmark.RING_FINGER_PIP].y])
    pinky_pip = np.array([hand_landmarks.landmark[mp_hands.HandLandmark.PINKY_PIP].x, 
                         hand_landmarks.landmark[mp_hands.HandLandmark.PINKY_PIP].y])
    
    wrist = np.array([hand_landmarks.landmark[mp_hands.HandLandmark.WRIST].x, 
                     hand_landmarks.landmark[mp_hands.HandLandmark.WRIST].y])
    
    # Calculate distances
    thumb_index_distance = np.linalg.norm(thumb_tip - index_tip)
    
    # Detect pointing gesture (index finger extended, others curled)
    pointing = (index_tip[1] < index_pip[1]) and (middle_tip[1] > middle_pip[1]) and (ring_tip[1] > ring_pip[1]) and (pinky_tip[1] > pinky_pip[1])
    
    # Detect pinch gesture (thumb and index finger close)
    pinching = thumb_index_distance < 0.1
    
    # Detect V sign (index and middle fingers extended, others curled)
    v_sign = (index_tip[1] < index_pip[1]) and (middle_tip[1] < middle_pip[1]) and (ring_tip[1] > ring_pip[1]) and (pinky_tip[1] > pinky_pip[1])
    
    # Detect palm (all fingers extended)
    palm = (index_tip[1] < index_pip[1]) and (middle_tip[1] < middle_pip[1]) and (ring_tip[1] < ring_pip[1]) and (pinky_tip[1] < pinky_pip[1])
    
    # Detect fist (all fingers curled)
    fist = (index_tip[1] > index_pip[1]) and (middle_tip[1] > middle_pip[1]) and (ring_tip[1] > ring_pip[1]) and (pinky_tip[1] > pinky_pip[1])
    
    # Determine screen coordinates normalized to [0,1]
    x, y = index_tip
    
    if pointing:
        return "point", x, y
    elif pinching:
        return "pinch", x, y
    elif v_sign:
        return "v_sign", x, y
    elif palm:
        return "palm", x, y
    elif fist:
        return "fist", x, y
    else:
        return "none", x, y

def main():
    try:
        with mp_hands.Hands(
            model_complexity=0,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.4,
            max_num_hands=2) as hands:
            
            # Add a help overlay flag
            show_help = True
            
            while cap.isOpened():
                success, image = cap.read()
                if not success:
                    print("Ignoring empty camera frame.")
                    continue
                    
                # Flip the image horizontally for a selfie-view display
                image = cv2.flip(image, 1)
                
                # To improve performance, optionally mark the image as not writeable
                image.flags.writeable = False
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                results = hands.process(image)
                
                # Draw the hand annotations on the image
                image.flags.writeable = True
                image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                
                # Create a help overlay
                if show_help:
                    # Draw semi-transparent overlay
                    help_overlay = image.copy()
                    cv2.rectangle(help_overlay, (0, 0), (width, 180), (0, 0, 0), -1)
                    image = cv2.addWeighted(help_overlay, 0.7, image, 0.3, 0)
                    
                    # Add gesture guide
                    cv2.putText(image, "GESTURE GUIDE:", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                    cv2.putText(image, "Point (1 finger): Select object", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
                    cv2.putText(image, "Pinch (thumb+index): Move object", (20, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
                    cv2.putText(image, "TWO V Signs: Duplicate object", (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
                    cv2.putText(image, "TWO Palms: Create new object", (20, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
                    cv2.putText(image, "TWO Fists: Delete selected object", (20, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
                    cv2.putText(image, "Press 'H' to hide help | ESC to exit", (width-300, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
                
                # Variables to store hand data
                hand1_data = None
                hand2_data = None
                
                if results.multi_hand_landmarks:
                    # Process all detected hands (up to 2)
                    for i, hand_landmarks in enumerate(results.multi_hand_landmarks[:2]):
                        mp_drawing.draw_landmarks(
                            image,
                            hand_landmarks,
                            mp_hands.HAND_CONNECTIONS,
                            mp_drawing_styles.get_default_hand_landmarks_style(),
                            mp_drawing_styles.get_default_hand_connections_style())
                        
                        try:
                            # Process hand landmarks for gestures
                            gesture, x, y = detect_gestures(hand_landmarks)
                            
                            # Convert normalized coordinates to pixel values
                            pixel_x, pixel_y = int(x * width), int(y * height)
                            
                            # Draw hand number and gesture type
                            hand_label = f"Hand {i+1}: {gesture}"
                            cv2.putText(image, hand_label, (10, 220+(30*i)), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                            
                            # Store hand data
                            if i == 0:
                                hand1_data = (gesture, x, y)
                            elif i == 1:
                                hand2_data = (gesture, x, y)
                        except Exception as e:
                            print(f"Error processing hand {i+1}: {e}")
                    
                    try:
                        # After processing all hands, send data to Blender
                        message = ""
                        if hand1_data:
                            gesture1, x1, y1 = hand1_data
                            message = f"{gesture1},{x1},{y1}"
                            
                            # If we also have hand2 data, append it
                            if hand2_data:
                                gesture2, x2, y2 = hand2_data
                                message += f",{gesture2},{x2},{y2}"
                        
                        # Send the message if we have at least one valid hand gesture
                        if message and hand1_data[0] != "none":
                            sock.sendto(message.encode(), blender_address)
                            print(f"Sent to Blender: {message}")
                    except Exception as e:
                        print(f"Error sending data to Blender: {e}")
                
                # Check for key presses
                key = cv2.waitKey(5) & 0xFF
                if key == 27:  # ESC key to exit
                    break
                elif key == ord('h') or key == ord('H'):  # 'H' key to toggle help
                    show_help = not show_help
                
                # Display the resulting frame
                cv2.imshow('Hand Gesture Control', image)
    except Exception as e:
        print(f"Error in main loop: {e}")
    finally:
        # Clean up resources
        cap.release()
        cv2.destroyAllWindows()
        sock.close()
        print("Resources released successfully")

if __name__ == "__main__":
    main()