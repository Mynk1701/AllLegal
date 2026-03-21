"""
PDF extraction utilities for legal case documents.
Extract text and metadata from PDF files.
"""
import PyPDF2
import logging
from typing import Optional, Dict
from pathlib import Path

logger = logging.getLogger(__name__)

class PDFExtractorService:
    """Type-safe PDF text and metadata extractor"""
    
    @staticmethod
    def extract_text(pdf_path: str) -> Optional[str]:
        """
        Extract all text from PDF file.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Extracted text or None if error
        """
        try:
            path = Path(pdf_path)
            if not path.exists():
                logger.error(f"❌ PDF file not found: {pdf_path}")
                return None
            
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ""
                for page_num, page in enumerate(reader.pages):
                    text += f"\n--- Page {page_num + 1} ---\n"
                    text += page.extract_text()
                
                logger.info(f"✅ Extracted text from {pdf_path} ({len(reader.pages)} pages)")
                return text
        except Exception as e:
            logger.error(f"❌ Error extracting PDF: {str(e)}")
            return None
    
    @staticmethod
    def extract_metadata(pdf_path: str) -> Dict:
        """
        Extract case metadata from PDF.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dictionary with extracted metadata
        """
        text = PDFExtractorService.extract_text(pdf_path)
        if not text:
            return {}
        
        # Extract first 500 chars as summary
        summary = text[:500].replace('\n', ' ').strip()
        
        return {
            "summary": summary,
            "text_length": len(text),
            "extracted_at": str(Path(pdf_path).stat().st_mtime)
        }

pdf_extractor_service = PDFExtractorService()
