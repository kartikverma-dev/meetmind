"""Magic bytes validator to verify file headers against claimed extensions."""

import logging

logger = logging.getLogger(__name__)

def verify_file_type(file_path: str, claimed_extension: str) -> bool:
    """
    Verify the actual file type by checking its magic bytes / header signatures.
    Supports MP3, MP4, WAV, MKV, WebM, Ogg, FLAC, AVI.
    """
    ext = claimed_extension.lower().strip(".")
    
    try:
        with open(file_path, "rb") as f:
            header = f.read(12)
    except IOError as exc:
        logger.error("Failed to read file for magic bytes validation: %s", exc)
        return False

    if not header:
        return False

    if ext == "mp3":
        # MP3 starts with ID3 (b"ID3") or frame sync (0xFF and 0xE0 mask for audio frames)
        return header.startswith(b"ID3") or (
            len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0
        )
    elif ext == "mp4":
        # MP4 has ftyp signature at bytes 4-8
        return len(header) >= 8 and header[4:8] == b"ftyp"
    elif ext == "wav":
        # WAV starts with RIFF header
        return header.startswith(b"RIFF")
    elif ext in ["mkv", "webm"]:
        # Matroska / WebM starts with EBML element identifier (0x1A 0x45 0xDF 0xA3)
        return header.startswith(b"\x1a\x45\xdf\xa3")
    elif ext == "ogg":
        # Ogg container format starts with OggS
        return header.startswith(b"OggS")
    elif ext == "flac":
        # Native FLAC files start with fLaC
        return header.startswith(b"fLaC")
    elif ext == "avi":
        # AVI starts with RIFF header
        return header.startswith(b"RIFF")
    
    # Allow fallback for unrecognized but allowed formats
    return True
