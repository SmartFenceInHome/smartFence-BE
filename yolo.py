from flask import Flask, request, jsonify
from ultralytics import YOLO
import cv2
import numpy as np
import base64
import torch

app = Flask(__name__)

yolo_base = YOLO('yolov8n.pt')
yolo_custom = YOLO('detect_model/best.pt')

coco_class_names = {0: 'person', 15: 'cat', 16: 'dog', 78: 'teddy bear'}
custom_class_names = {0: 'OldPeople', 1: 'baby'}

correct_predictions = {cls: 0 for cls in coco_class_names}
total_predictions = {cls: 0 for cls in coco_class_names}

correct_predictions_custom = {cls: 0 for cls in custom_class_names}
total_predictions_custom = {cls: 0 for cls in custom_class_names}

actual_classes = list(coco_class_names.keys()) + list(custom_class_names.keys())

def get_class_name(cls, is_custom):
    if is_custom:
        return custom_class_names.get(cls, "unknown")
    else:
        return coco_class_names.get(cls, "unknown")
    

@app.route('/detect', methods=['POST'])
def detect_objects():
    try:
        # base64 이미지 디코딩
        image_data = base64.b64decode(request.json['image'])
        nparr = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        results_base = yolo_base(image, conf=0.25)
        results_custom = yolo_custom(image, conf=0.25)

        boxes_base = results_base[0].boxes
        boxes_custom = results_custom[0].boxes

        merged_boxes = torch.cat([boxes_base.data, boxes_custom.data], dim=0)

        for box in merged_boxes:
            x1, y1, x2, y2, conf, cls = box.tolist()
            x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])
            cls = int(cls)

            if cls in coco_class_names:
                total_predictions[cls] += 1
                correct_predictions[cls] += 1
                label = f"{get_class_name(cls, False)} {conf:.2f}"  # COCO 클래스용
            
            if cls in custom_class_names:
                total_predictions_custom[cls] += 1
                correct_predictions_custom[cls] += 1
                label = f"{get_class_name(cls, True)} {conf:.2f}"  # 커스텀 클래스용

            print(label)

            for cls in coco_class_names:
                accuracy = (correct_predictions[cls] / total_predictions[cls]) * 100 if total_predictions[cls] > 0 else 0
                print(f"COCO Class {get_class_name(cls, is_custom=False)} - Accuracy: {accuracy:.2f}%")

            for cls in custom_class_names:
                accuracy = (correct_predictions_custom[cls] / total_predictions_custom[cls]) * 100 if total_predictions_custom[cls] > 0 else 0
                print(f"Custom Class {get_class_name(cls, is_custom=True)} - Accuracy: {accuracy:.2f}%")
        
        total_detections = len(boxes_base) + len(boxes_custom)
        detected = total_detections > 0
        print('total_detections :', total_detections)
        
        return jsonify({
            'detected': detected,
            'object_count': total_detections
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)