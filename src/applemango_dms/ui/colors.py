# Brand Colors
ROYAL_BLUE = '#3447AA'
POWDER_PINK = '#FBEAEB'

# Background
BACKGROUND = '#F0F0F0'

# Surfaces
SURFACE = '#FBFBFB'
SURFACE_ALT = '#FFFFFF'
SURFACE_ALT2 = '#F0F0F0'
SURFACE_ACCENT_SOFT = '#EDF2FB'
SURFACE_HOVER = '#F6F8FC'
SURFACE_HOVER_SOFT = '#EEF2FB'
SURFACE_DANGER_HOVER = '#FFF1F1'

# Number Badge
NUMBER_DESIGNATION_BG = SURFACE_HOVER

# Borders
BORDER = '#E4E8F1'
BORDER_SOFT = '#D7DEEA'
BORDER_LIGHT = '#D9DEEA'
BORDER_INPUT = '#C8D0E6'

# Text
TEXT_PRIMARY = '#222831'
TEXT_SECONDARY = '#6B7280'
TEXT_INVERSE = '#FAFAFA'
TEXT_EMPHASIS = '#1F2B4A'
TEXT_PLACEHOLDER = '#8F96AD'
TEXT_SUBTLE = '#5C667F'

# Text Accent
TEXT_TINT = '#2D3448'
TEXT_TINT_HOVER = '#2B3348'
TEXT_ON_PRIMARY_SOFT = '#F3F2FF'
TEXT_NEUTRAL_DARK = '#111111'

# Interactive
PRIMARY = ROYAL_BLUE
PRIMARY_HOVER = '#2E3F97'
PRIMARY_PRESSED = PRIMARY
PRIMARY_ACTION_HOVER = '#245BC0'

SECONDARY = '#7287E5'
SECONDARY_STRONG = '#5555D5'
SECONDARY_STRONG_HOVER = '#5E64E6'
SECONDARY_ACTIVE = '#6973FF'
SECONDARY_GLOW = '#7D86FF'
SECONDARY_GLOW_STRONG = '#9AA7FF'
SECONDARY_SOFT = '#ECE9FF'

ACCENT = POWDER_PINK

# Status
SUCCESS = '#2ca24d'
SUCCESS_STRONG = '#2E9B53'
FAILED = '#d23b3b'
FAILED_STRONG = '#D33E3E'
FAILED_HOVER = '#BF3232'
ALERT = '#FF4F00'
PROCESSING = '#2d6cdf'
STANDBY = '#000000'
ROW_SELECTED_SEPARATOR = '#7070E5'

# Badge color maps
# Value tuple format: (text_color, background_color)
FILE_TYPE_COLORS = {
	'pdf': ('#EF4444', '#FDE9E9'),
	'doc': ('#2563EB', '#E5ECFD'),
	'docx': ('#2563EB', '#E5ECFD'),
	'hwp': ('#2563EB', '#E5ECFD'),
	'xls': ('#16A34A', '#E3F4E9'),
	'xlsx': ('#16A34A', '#E3F4E9'),
	'xlsm': ('#16A34A', '#E3F4E9'),
	'csv': ('#0F766E', '#E2EFEE'),
	'ppt': ('#F97316', '#FEEEE3'),
	'pptx': ('#F97316', '#FEEEE3'),
	'pptm': ('#F97316', '#FEEEE3'),
	'txt': ('#64748B', '#ECEEF1'),
	'jpg': ('#8B5CF6', '#F1EBFE'),
	'jpeg': ('#8B5CF6', '#F1EBFE'),
	'png': ('#8B5CF6', '#F1EBFE'),
	'gif': ('#8B5CF6', '#F1EBFE'),
	'tif': ('#8B5CF6', '#F1EBFE'),
	'tiff': ('#8B5CF6', '#F1EBFE'),
	'webp': ('#8B5CF6', '#F1EBFE'),
	'svg': ('#8B5CF6', '#F1EBFE'),
	'zip': ('#6B7280', '#EDEEF0'),
	'7z': ('#6B7280', '#EDEEF0'),
	'rar': ('#6B7280', '#EDEEF0'),
	'tar': ('#6B7280', '#EDEEF0'),
	'gz': ('#6B7280', '#EDEEF0'),
	'mp4': ('#4F46E5', '#EAE9FC'),
	'mov': ('#4F46E5', '#EAE9FC'),
	'avi': ('#4F46E5', '#EAE9FC'),
	'wmv': ('#4F46E5', '#EAE9FC'),
	'mkv': ('#4F46E5', '#EAE9FC'),
	'mp3': ('#DB2777', '#FBE5EF'),
	'wma': ('#DB2777', '#FBE5EF'),
	'm4a': ('#DB2777', '#FBE5EF'),
	'exe': ('#B45309', '#F6EAE1'),
	'msi': ('#B45309', '#F6EAE1'),
	'bat': ('#B45309', '#F6EAE1'),
	'cmd': ('#B45309', '#F6EAE1'),
	'psd': ('#C026D3', '#F7E5FA'),
	'ai': ('#C026D3', '#F7E5FA'),
	'indd': ('#C026D3', '#F7E5FA'),
	'xd': ('#C026D3', '#F7E5FA'),
	'db': ('#0891B2', '#E1F2F6'),
	'sqlite': ('#0891B2', '#E1F2F6'),
	'mdb': ('#0891B2', '#E1F2F6'),
	'accdb': ('#0891B2', '#E1F2F6'),
	'html': ('#EA580C', '#FCEBE2'),
	'htm': ('#EA580C', '#FCEBE2'),
}

DEFAULT_FILE_TYPE_COLOR = ('#64748B', '#ECEEF1')

DOCUMENT_TYPE_COLORS = {
	'서류': ('#4B5563', '#E9EBEC'),
	'양식': ('#34A853', '#E7F5EA'),
	'공문': ('#D14343', '#F9E8E8'),
	'회계': ('#F59E0B', '#FEF3E2'),
	'명부': ('#8B5CF6', '#F1EBFE'),
	'사진': ('#3B82F6', '#E7F0FE'),
	'영상': ('#4F46E5', '#EAE9FC'),
	'녹음': ('#06B6D4', '#E1F6FA'),
	'디자인': ('#EAB308', '#FCF6E1'),
	'교육': ('#2E8B57', '#E6F1EB'),
	'일정': ('#3447AA', '#E7E9F5'),
	'프로젝트': ('#F97316', '#FEEEE3'),
	'홍보': ('#EC4899', '#FDE9F3'),
	'자산': ('#8B5E3C', '#F1ECE8'),
	'인사': ('#7C3AED', '#EFE7FD'),
	'기록': ('#9F1239', '#F3E3E7'),
	'지도': ('#0F766E', '#E2EFEE'),
	'기타': ('#9CA3AF', '#F3F4F5'),
}

DEFAULT_DOCUMENT_TYPE_COLOR = ('#9CA3AF', '#F3F4F5')