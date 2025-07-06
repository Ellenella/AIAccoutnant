
import os
import groq
from typing import Optional, Dict
import json
import dotenv
from datetime import datetime
import base64
import pytesseract
from PIL import Image
import io
import pdf2image
import tempfile

# Load environment variables
dotenv.load_dotenv()

class GroqClient:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not found in environment variables")
        self.client = groq.Client(api_key=api_key)
        pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'  # Update path as needed

    def _extract_text_from_pdf(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF using OCR"""
        try:
            images = pdf2image.convert_from_bytes(pdf_bytes)
            text = ""
            for i, image in enumerate(images):
                text += f"Page {i+1}:\n"
                text += pytesseract.image_to_string(image) + "\n\n"
            return text.strip()
        except Exception as e:
            print(f"PDF extraction error: {e}")
            return ""

    def _extract_text_from_image(self, image_bytes: bytes) -> str:
        """Extract text from image using OCR"""
        try:
            image = Image.open(io.BytesIO(image_bytes))
            return pytesseract.image_to_string(image)
        except Exception as e:
            print(f"Image OCR error: {e}")
            return ""

    def process_receipt(self, file_bytes: Optional[bytes] = None, text: str = "", file_type: str = None) -> Dict:
        """
        Process receipt from various formats with OCR fallback
        Supported file_types: 'pdf', 'image', 'text'
        """
        # Extract text from file if provided
        extracted_text = text
        if file_bytes and file_type:
            if file_type == 'pdf':
                extracted_text = self._extract_text_from_pdf(file_bytes)
            elif file_type in ['jpg', 'jpeg', 'png']:
                extracted_text = self._extract_text_from_image(file_bytes)
        
        # Prepare the prompt
        prompt = """check if there is only or many receipts and if there is morethan one 
        Analyze the receipt one by one and extract structured data for each of the receipts:
1. Total amount (with confidence score 0-1)
2. Merchant name (with confidence)
3. Transaction date (YYYY-MM-DD format)
4. Category (with confidence)
5. Line items (description, amount, quantity)

Categories: [Meals, Travel, Office, Software, Rent, Utilities, Other]

Respond with this exact JSON structure:
{
    "amount": {"value": float, "confidence": float},
    "merchant": {"value": str, "confidence": float},
    "date": {"value": str, "confidence": float},
    "category": {"value": str, "confidence": float},
    "description": str,
    "line_items": [
        {
            "description": str,
            "amount": float,
            "quantity": int
        }
    ]
}"""

        try:
            messages = [{
                "role": "user",
                "content": prompt + f"\n\nExtracted Receipt Text:\n{extracted_text}"
            }]

            # Include image data if available (for better accuracy)
            if file_bytes and file_type in ['jpg', 'jpeg', 'png']:
                encoded_image = base64.b64encode(file_bytes).decode('utf-8')
                messages.append({
                    "role": "user",
                    "content": f"data:image/{file_type};base64,{encoded_image}"
                })

            response = self.client.chat.completions.create(
                model="llama3-70b-8192",
                messages=messages,
                temperature=0.1,
                response_format={"type": "json_object"},
                max_tokens=2000
            )

            result = json.loads(response.choices[0].message.content)
            return self._validate_response(result, extracted_text)

        except Exception as e:
            print(f"Processing error: {e}")
            return self._error_response(extracted_text)
    
    def _validate_response(self, data: Dict, original_desc: str) -> Dict:
        """Ensure response meets expected format"""
        validated = {
            "amount": {"value": 0.0, "confidence": 0},
            "merchant": {"value": "", "confidence": 0},
            "date": {"value": "", "confidence": 0},
            "category": {"value": "Other", "confidence": 0},
            "description": original_desc,
            "line_items": []
        }
        
        try:
            # Validate amount
            if 'amount' in data:
                validated['amount'] = {
                    "value": float(data['amount'].get('value', 0)),
                    "confidence": min(1.0, max(0, float(data['amount'].get('confidence', 0))))
                }
            
            # Validate merchant
            if 'merchant' in data:
                validated['merchant'] = {
                    "value": str(data['merchant'].get('value', '')),
                    "confidence": min(1.0, max(0, float(data['merchant'].get('confidence', 0))))
                }
            
            # Validate date
            if 'date' in data:
                date_str = str(data['date'].get('value', ''))
                try:
                    datetime.strptime(date_str, '%Y-%m-%d')
                    validated['date'] = {
                        "value": date_str,
                        "confidence": min(1.0, max(0, float(data['date'].get('confidence', 0))))
                    }
                except ValueError:
                    pass
            
            # Validate category
            valid_categories = ["Meals", "Travel", "Office", "Software", "Rent", "Utilities", "Other"]
            if 'category' in data:
                cat = str(data['category'].get('value', 'Other'))
                validated['category'] = {
                    "value": cat if cat in valid_categories else "Other",
                    "confidence": min(1.0, max(0, float(data['category'].get('confidence', 0))))
                }
            
            # Preserve line items if provided
            if 'line_items' in data and isinstance(data['line_items'], list):
                validated['line_items'] = [
                    {
                        "description": str(item.get('description', '')),
                        "amount": float(item.get('amount', 0)),
                        "quantity": int(item.get('quantity', 1))
                    } for item in data['line_items']
                ]
            
            return validated
            
        except Exception as e:
            print(f"Validation error: {e}")
            return validated
    
    def _error_response(self, description: str) -> Dict:
        """Default error response"""
        return {
            "amount": {"value": 0.0, "confidence": 0},
            "merchant": {"value": "", "confidence": 0},
            "date": {"value": "", "confidence": 0},
            "category": {"value": "Other", "confidence": 0},
            "description": description,
            "line_items": []
        }