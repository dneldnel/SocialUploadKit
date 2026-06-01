from __future__ import annotations

UPLOAD_URL = "https://creator.douyin.com/creator-micro/content/upload"
CREATOR_HOME_URL = "https://creator.douyin.com/"
LOGIN_DONE_URL_PREFIX = "https://creator.douyin.com/creator-micro/home"
VIDEO_PUBLISH_URLS = (
    "https://creator.douyin.com/creator-micro/content/publish?enter_from=publish_page",
    "https://creator.douyin.com/creator-micro/content/post/video?enter_from=publish_page",
)
MANAGE_URL_PATTERN = "https://creator.douyin.com/creator-micro/content/manage**"
NOTE_PUBLISH_URL_PATTERN = "**/creator-micro/content/post/image?**"
NOTE_MANAGE_URL_PATTERN = "**/creator-micro/content/manage?enter_from=publish**"

TEXT_LOGIN_PHONE = "手机号登录"
TEXT_LOGIN_SCAN = "扫码登录"
TEXT_QRCODE_EXPIRED = "二维码失效"
TEXT_GOT_IT = "我知道了"
TEXT_DESCRIPTION = "作品描述"
TEXT_SCHEDULE = "定时发布"
TEXT_VISIBILITY_PUBLIC = "公开"
TEXT_VISIBILITY_PRIVATE = "仅自己可见"
TEXT_PUBLISH = "发布"
TEXT_PUBLISH_NOTE = "发布图文"
TEXT_SELECT_COVER = "选择封面"
TEXT_COVER_REQUIRED = "请设置封面后再发布"
TEXT_COVER_CONFIRM = "是否确认应用此封面？"
TEXT_CONFIRM = "确定"
TEXT_DONE = "完成"
TEXT_ADD_LABEL = "添加标签"
TEXT_CART = "购物车"
TEXT_PRODUCT_NOT_FOUND = "未搜索到对应商品"

QRCODE_IMG = 'img[aria-label="二维码"]'
UPLOAD_VIDEO_INPUT = "div[class^='container'] input"
UPLOAD_VIDEO_RETRY_INPUT = 'div.progress-div [class^="upload-btn-input"]'
UPLOAD_IMAGE_INPUT = "div[class^='container'] input[accept*='image']"
VIDEO_UPLOADED_MARKER = '[class^="long-card"] div:has-text("重新上传")'
VIDEO_UPLOAD_FAILED = 'div.progress-div > div:has-text("上传失败")'
TITLE_INPUT = 'input[type="text"]'
DESCRIPTION_EDITOR = '.zone-container[contenteditable="true"]'
SCHEDULE_RADIO = f"label[class^='radio']:has-text('{TEXT_SCHEDULE}'), [class^='radio']:has-text('{TEXT_SCHEDULE}')"
DATE_TIME_INPUT = '.semi-input[placeholder="日期和时间"]'
LOCATION_SELECT = 'div.semi-select span:has-text("输入地理位置")'
LOCATION_OPTION = 'div[role="listbox"] [role="option"]'
PRODUCT_SHORT_TITLE = 'input[placeholder="请输入商品短标题"]'
PRODUCT_FINISH_BUTTON = 'button:has-text("完成编辑")'
PRODUCT_CANCEL_BUTTON = 'button:has-text("取消")'
PRODUCT_LINK_INPUT = 'input[placeholder="粘贴商品链接"]'
PRODUCT_ADD_LINK = 'span:has-text("添加链接")'
MODAL_CLOSE = ".semi-modal-close"
MODAL_CONTENT = ".semi-modal-content"
COVER_MODAL = 'div[id*="creator-content-modal"]'
COVER_UPLOAD_INPUT = "div[class^='semi-upload upload'] >> input.semi-upload-hidden-input"
COVER_STEP = "div[class*='steps'] div"
COVER_DONE = 'button:visible:has-text("完成")'
COVER_FOOTER = "div.extractFooter"
COVER_BLOCKING_LAYER = (
    'div[class*="dy-creator-content-modal-wrap"], '
    'div[class*="dy-creator-content-portal"] div[class*="coverImgContainer"], '
    'div[class*="dy-creator-content-portal"] div.extractFooter'
)
RECOMMEND_COVER = '[class^="recommendCover-"]'
THIRD_PARTY_SWITCH = '[class^="info"] > [class^="first-part"] div div.semi-switch'
THIRD_PARTY_SWITCH_INPUT = "input.semi-switch-native-control"
VISIBILITY_RADIO = "label[class^='radio']:has-text('{label}')"
