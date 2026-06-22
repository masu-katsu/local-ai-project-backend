import logging
from typing import Dict, Any, Optional
import base64
import io
from PIL import Image
import os

logger = logging.getLogger(__name__)

class VisionProcessor:
    """画像処理システム"""
    
    def __init__(self):
        logger.info("VisionProcessor初期化")
        self.ocr_available = False
        self.yolo_available = False
        self._try_load_models()
    
    def _try_load_models(self):
        """Visionモデルをロード（オプション）"""
        try:
            # OCRモデルのロード（tesseract/pytesseract）
            try:
                import pytesseract
                self.pytesseract = pytesseract
                self.ocr_available = True
                logger.info("OCRモデルロード完了 (tesseract)")
            except ImportError:
                logger.warning("pytesseract未インストール - OCR機能無効")
            
            # YOLOモデルのロード
            try:
                import torch
                from ultralytics import YOLO
                self.yolo_model = YOLO('yolov8n.pt')  # 軽量モデル
                self.yolo_available = True
                logger.info("YOLOモデルロード完了")
            except ImportError:
                logger.warning("ultralytics未インストール - 物体検出機能無効")
            except Exception as e:
                logger.warning(f"YOLOモデルロード失敗: {e}")
                
        except Exception as e:
            logger.warning(f"Visionモデルロード失敗: {e} - 簡易モードで動作")
    
    async def analyze_image(
        self,
        image_data: bytes,
        task: str = "describe"
    ) -> Dict[str, Any]:
        """
        画像を分析
        
        Args:
            image_data: 画像データ
            task: タスク種別 (describe, ocr, detect)
        
        Returns:
            分析結果
        """
        logger.info(f"画像分析: {task} - {len(image_data)} bytes")
        
        try:
            # 画像データをPIL Imageに変換
            image = Image.open(io.BytesIO(image_data))
            
            # 画像の基本情報を取得
            width, height = image.size
            format = image.format
            mode = image.mode
            
            if task == "describe":
                return await self._describe_image(image, width, height, format, mode)
            elif task == "ocr":
                return await self._extract_text(image)
            elif task == "detect":
                return await self._detect_objects(image, width, height)
            else:
                return {"error": f"Unknown task: {task}"}
                
        except Exception as e:
            logger.error(f"画像分析失敗: {e}")
            return {"error": str(e)}

    async def _describe_image(self, image: Image.Image, width: int, height: int, format: str, mode: str) -> Dict[str, Any]:
        """画像を説明"""
        # 簡易的な画像分析（実際のVisionモデルを使用すべき）
        description = f"画像サイズ: {width}x{height}, フォーマット: {format}, モード: {mode}"
        
        # 色情報の分析
        if mode == "RGB":
            description += ", カラー画像"
        elif mode == "L":
            description += ", グレースケール画像"
        elif mode == "RGBA":
            description += ", アルファチャンネル付きカラー画像"
        
        return {
            "description": description,
            "width": width,
            "height": height,
            "format": format,
            "mode": mode,
            "confidence": 0.9
        }

    async def _extract_text(self, image: Image.Image) -> Dict[str, Any]:
        """テキストを抽出（OCR）"""
        try:
            if self.ocr_available:
                # tesseractを使用してOCRを実行
                text = self.pytesseract.image_to_string(image, lang='jpn+eng')
                return {
                    "text": text.strip(),
                    "confidence": 0.9,
                    "method": "tesseract"
                }
            else:
                # フォールバック
                text = "OCR機能は簡易実装です。実際のOCRライブラリ（tesseractなど）を統合してください。"
                return {
                    "text": text,
                    "confidence": 0.5,
                    "note": "簡易実装 - 実際のOCRライブラリが必要"
                }
        except Exception as e:
            return {
                "text": "",
                "error": str(e),
                "note": "OCRライブラリが利用できません"
            }

    async def _detect_objects(self, image: Image.Image, width: int, height: int) -> Dict[str, Any]:
        """物体を検出"""
        try:
            if self.yolo_available:
                # YOLOを使用して物体検出を実行
                results = self.yolo_model(image)
                
                objects = []
                for result in results:
                    for box in result.boxes:
                        # バウンディングボックス座標
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        confidence = box.conf[0].item()
                        class_id = int(box.cls[0].item())
                        class_name = self.yolo_model.names[class_id]
                        
                        objects.append({
                            "name": class_name,
                            "confidence": confidence,
                            "bbox": [x1, y1, x2, y2]
                        })
                
                return {
                    "objects": objects,
                    "count": len(objects),
                    "method": "yolov8"
                }
            else:
                # フォールバック
                objects = [
                    {"name": "image", "confidence": 1.0, "bbox": [0, 0, width, height]}
                ]
                
                return {
                    "objects": objects,
                    "count": len(objects),
                    "note": "簡易実装 - 実際の物体検出モデルが必要"
                }
        except Exception as e:
            return {
                "objects": [],
                "error": str(e),
                "note": "物体検出ライブラリが利用できません"
            }
