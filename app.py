import streamlit as st
import fitz
import zipfile
import random
import string
from datetime import date
from fpdf import FPDF
from io import BytesIO
from PIL import Image

st.set_page_config(page_title="KDPEasy Activity Creator", page_icon="🧩", layout="centered")

# Password -> expiry date, or None for permanent access (paying customers).
PASSWORD_EXPIRY = {
    "KDPACT2026": None,
}

MARGIN = 0.5
TITLE_H = 0.5
GAP = 0.15

PAGE_SIZES = {
    "Letter (8.5 x 11 in)": (8.5, 11.0),
    "Square (8.5 x 8.5 in)": (8.5, 8.5),
    "8 x 10 in": (8.0, 10.0),
    "6 x 9 in": (6.0, 9.0),
    "A4": (8.27, 11.69),
    "A5": (5.83, 8.27),
}


# Fixed high-contrast look, optimized for black & white KDP interior printing
# (color themes were removed — a colored title band just turns into a gray
# block once printed in B&W, which is how nearly every word search book ships).
THEME = {"primary": (0, 0, 0), "text": (0, 0, 0)}

# Preset word banks so customers can pick a topic instead of typing every word themselves.
WORD_THEMES = {
    "Farm Animals": [
        "COW", "PIG", "HORSE", "SHEEP", "GOAT", "CHICKEN", "DUCK", "TURKEY",
        "ROOSTER", "DONKEY", "RABBIT", "GOOSE", "LAMB", "PONY", "BULL", "HEN",
        "BARN", "TRACTOR", "FIELD", "HAYSTACK", "FARMER", "STABLE", "PASTURE", "SADDLE",
    ],
    "Ocean & Sea Life": [
        "SHARK", "WHALE", "DOLPHIN", "OCTOPUS", "STARFISH", "JELLYFISH", "CRAB",
        "LOBSTER", "SEAHORSE", "TURTLE", "CORAL", "SEAWEED", "CLAM", "OYSTER",
        "STINGRAY", "EEL", "PENGUIN", "SEAL", "WALRUS", "ANCHOR", "WAVE", "TIDE", "REEF", "PEARL",
    ],
    "Dinosaurs": [
        "TREX", "RAPTOR", "TRICERATOPS", "STEGOSAURUS", "PTERODACTYL", "BRONTOSAURUS",
        "FOSSIL", "VOLCANO", "JUNGLE", "EXTINCT", "SKELETON", "CLAW", "SCALES", "EGG",
        "NEST", "PREHISTORIC", "SWAMP", "HERBIVORE", "CARNIVORE", "ANCIENT", "ROAR", "TAIL", "SPIKE", "HORN",
    ],
    "Space & Astronauts": [
        "ROCKET", "PLANET", "ASTRONAUT", "GALAXY", "COMET", "METEOR", "SATELLITE",
        "ORBIT", "MOON", "STAR", "MARS", "JUPITER", "SATURN", "NEBULA", "TELESCOPE",
        "SPACESHIP", "ALIEN", "CRATER", "GRAVITY", "COSMOS", "UNIVERSE", "SHUTTLE", "LAUNCH", "SUNLIGHT",
    ],
    "Jungle & Safari": [
        "LION", "TIGER", "ELEPHANT", "GIRAFFE", "ZEBRA", "MONKEY", "GORILLA",
        "LEOPARD", "CHEETAH", "HIPPO", "RHINO", "CROCODILE", "PARROT", "SNAKE",
        "JUNGLE", "VINE", "WATERFALL", "SAFARI", "HYENA", "ANTELOPE", "TOUCAN", "JAGUAR", "PANTHER", "BAMBOO",
    ],
    "Sports": [
        "SOCCER", "BASKETBALL", "BASEBALL", "TENNIS", "HOCKEY", "GOLF", "SWIMMING",
        "RUNNING", "CYCLING", "BOXING", "WRESTLING", "VOLLEYBALL", "FOOTBALL",
        "CRICKET", "RUGBY", "SKATING", "SURFING", "SKIING", "MARATHON", "REFEREE", "TROPHY", "STADIUM", "COACH", "ATHLETE",
    ],
    "Food & Cooking": [
        "PIZZA", "BURGER", "PASTA", "SALAD", "SANDWICH", "PANCAKE", "COOKIE",
        "CHOCOLATE", "CUPCAKE", "BREAD", "CHEESE", "SOUP", "NOODLES", "TACO",
        "SUSHI", "WAFFLE", "DONUT", "MUFFIN", "YOGURT", "HONEY", "BUTTER", "RECIPE", "KITCHEN", "OVEN",
    ],
    "Holidays & Christmas": [
        "SANTA", "REINDEER", "SNOWMAN", "ORNAMENT", "STOCKING", "CANDLE", "WREATH",
        "MISTLETOE", "SLEIGH", "CHIMNEY", "GARLAND", "TINSEL", "CAROL", "GINGERBREAD",
        "ELF", "PRESENT", "HOLLY", "WINTER", "SNOWFLAKE", "FIREPLACE", "JINGLE", "NUTCRACKER", "ICICLE", "MITTEN",
    ],
    "Weather & Seasons": [
        "SUNSHINE", "RAINBOW", "THUNDER", "LIGHTNING", "CLOUD", "BREEZE", "STORM",
        "SNOW", "FROST", "HUMID", "DROUGHT", "TORNADO", "HURRICANE", "FORECAST",
        "AUTUMN", "SPRING", "SUMMER", "WINTER", "BLIZZARD", "DRIZZLE", "FOG", "HAIL", "MIST", "TEMPERATURE",
    ],
    "School Days": [
        "PENCIL", "NOTEBOOK", "TEACHER", "CLASSROOM", "HOMEWORK", "BACKPACK",
        "LIBRARY", "LOCKER", "RECESS", "PLAYGROUND", "PRINCIPAL", "SCISSORS",
        "CRAYON", "MARKER", "RULER", "ALPHABET", "SCIENCE", "HISTORY", "READING", "LUNCHBOX", "SCHOOLBUS", "CHALKBOARD", "ASSIGNMENT", "STUDENT",
    ],
}

# Short visual-scene hints used to build a cover-art AI image prompt per theme.
COVER_THEME_HINTS = {
    "Farm Animals": "a cheerful farmyard scene with a cow, pig, chickens, and a red barn under a sunny blue sky",
    "Ocean & Sea Life": "a colorful underwater scene with a dolphin, tropical fish, and a coral reef",
    "Dinosaurs": "friendly cartoon dinosaurs in a lush prehistoric jungle landscape",
    "Space & Astronauts": "a fun outer-space scene with planets, stars, and a cartoon astronaut floating by a rocket",
    "Jungle & Safari": "a lively jungle safari scene with a lion, an elephant, and tropical plants",
    "Sports": "kids happily playing soccer, basketball, and swimming in a colorful park",
    "Food & Cooking": "a colorful spread of fun foods like pizza, cupcakes, and fruit",
    "Holidays & Christmas": "a festive Christmas scene with Santa, a decorated tree, and falling snow",
    "Weather & Seasons": "a whimsical scene showing sunshine, rain, snow, and a rainbow together",
    "School Days": "a fun classroom scene with books, pencils, a backpack, and a school bus",
}


def build_cover_prompt(book_title, theme_choice, page_w, page_h):
    subject = COVER_THEME_HINTS.get(theme_choice, "a fun, colorful puzzle-book theme")
    title_text = book_title.strip() if book_title.strip() else "WORD SEARCH"
    orientation = "portrait" if page_h >= page_w else "landscape"
    trim_w = f"{page_w:g}"
    trim_h = f"{page_h:g}"
    return (
        f"Create a vibrant, full-color book cover illustration for a kids' WORD SEARCH puzzle book. "
        f"Make it immediately obvious this is a word search / puzzle book - for example, weave a few "
        f"large playful scattered letters or a faint word-search letter-grid pattern into the background "
        f"or border of the scene, without covering the main illustration. "
        f'Scene: {subject}. Bright, cheerful, high-contrast colors, playful cartoon illustration style, '
        f"friendly and inviting for kids and parents browsing an online bookstore. "
        f'Include the title "{title_text}" in bold, playful, easy-to-read lettering, designed as part of '
        f"the cover artwork (not added afterward). "
        f"{orientation.capitalize()} book cover, proportioned for a {trim_w} x {trim_h} inch page. No watermarks."
    )


CUSTOM_CSS = """
<style>
:root {
    color-scheme: light;
}
.stApp {
    background: linear-gradient(135deg, #eef2ff 0%, #ffffff 60%);
}
.kdp-card {
    background: white;
    border-radius: 16px;
    padding: 2rem 2rem 1.5rem;
    box-shadow: 0 4px 24px rgba(79, 70, 229, 0.08);
    margin-bottom: 1.5rem;
}
h1, h2, h3 { color: #4f46e5; }
.stButton>button, .stDownloadButton>button {
    background-color: #10b981;
    color: white;
    border-radius: 10px;
    border: none;
    padding: 0.6rem 1.4rem;
    font-weight: 600;
}
.stButton>button:hover, .stDownloadButton>button:hover {
    background-color: #059669;
    color: white;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def check_password() -> bool:
    if st.session_state.get("authed"):
        return True
    st.markdown('<div class="kdp-card">', unsafe_allow_html=True)
    st.title("🧩 KDPEasy Activity Creator")
    pw = st.text_input("Enter access password", type="password")
    if st.button("Unlock"):
        if pw in PASSWORD_EXPIRY:
            expiry = PASSWORD_EXPIRY[pw]
            if expiry is None or date.today() <= expiry:
                st.session_state["authed"] = True
                st.rerun()
            else:
                st.error("This trial password has expired. Please reach out to get full access.")
        else:
            st.error("Incorrect password.")
    st.markdown('</div>', unsafe_allow_html=True)
    return False


def tint_toward_white(color, amount=0.85):
    r, g, b = color
    return (
        int(r + (255 - r) * amount),
        int(g + (255 - g) * amount),
        int(b + (255 - b) * amount),
    )


def prepare_photo(uploaded_file, box_w, box_h, fill_mode):
    uploaded_file.seek(0)
    img = Image.open(uploaded_file).convert("RGB")
    target_ratio = box_w / box_h
    img_ratio = img.width / img.height

    if fill_mode:
        if img_ratio > target_ratio:
            new_w = int(img.height * target_ratio)
            left = (img.width - new_w) // 2
            img = img.crop((left, 0, left + new_w, img.height))
        else:
            new_h = int(img.width / target_ratio)
            top = (img.height - new_h) // 2
            img = img.crop((0, top, img.width, top + new_h))
        return img, box_w, box_h
    else:
        if img_ratio > target_ratio:
            draw_w = box_w
            draw_h = box_w / img_ratio
        else:
            draw_h = box_h
            draw_w = box_h * img_ratio
        return img, draw_w, draw_h


# ---------- Word Search ----------

WS_DIRECTIONS_EASY = [(0, 1), (1, 0)]
WS_DIRECTIONS_HARD = [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)]


def generate_word_search(words, grid_size, hard_mode=False, max_attempts=300):
    words = [w.strip().upper().replace(" ", "") for w in words if w.strip()]
    words = [w for w in words if w.isalpha() and len(w) <= grid_size]
    words = sorted(set(words), key=len, reverse=True)
    grid = [[None] * grid_size for _ in range(grid_size)]
    placements = {}
    skipped = []
    directions = WS_DIRECTIONS_HARD if hard_mode else WS_DIRECTIONS_EASY

    for word in words:
        placed = False
        for _ in range(max_attempts):
            dr, dc = random.choice(directions)
            r0 = random.randint(0, grid_size - 1)
            c0 = random.randint(0, grid_size - 1)
            r1 = r0 + dr * (len(word) - 1)
            c1 = c0 + dc * (len(word) - 1)
            if not (0 <= r1 < grid_size and 0 <= c1 < grid_size):
                continue
            cells = [(r0 + dr * i, c0 + dc * i) for i in range(len(word))]
            if all(grid[r][c] in (None, ch) for (r, c), ch in zip(cells, word)):
                for (r, c), ch in zip(cells, word):
                    grid[r][c] = ch
                placements[word] = cells
                placed = True
                break
        if not placed:
            skipped.append(word)

    for r in range(grid_size):
        for c in range(grid_size):
            if grid[r][c] is None:
                grid[r][c] = random.choice(string.ascii_uppercase)

    return grid, placements, skipped


def draw_word_search_page(pdf, page_w, page_h, theme, title, grid, word_list, show_solution, placements):
    primary = theme["primary"]
    text_color = theme["text"]

    pdf.add_page()
    content_w = page_w - 2 * MARGIN

    # Plain centered title, no colored band (matches the reference layout)
    pdf.set_text_color(*text_color)
    pdf.set_font("Helvetica", "B", 22 if page_w >= 7 else 18)
    pdf.set_xy(MARGIN, MARGIN)
    pdf.cell(content_w, TITLE_H, title, align="C")

    # Work out the word-bank column layout FIRST (it doesn't depend on the
    # grid's cell size) so its height can be reserved before sizing the grid.
    pdf.set_font("Helvetica", "B", 14)
    words_sorted = sorted(word_list)
    n = len(words_sorted)
    row_h = 0.32
    col_gap = 0.3
    pad = 0.3
    max_word_w = max((pdf.get_string_width(w) for w in words_sorted), default=0)
    min_col_w = max_word_w + pad
    num_cols_wanted = max(2, min(4, -(-n // 5)))
    max_cols_fit = max(1, int((content_w + col_gap) // (min_col_w + col_gap)))
    num_cols = max(1, min(num_cols_wanted, max_cols_fit))
    num_rows = -(-n // num_cols) if num_cols else 0
    col_w = min((content_w - (num_cols - 1) * col_gap) / num_cols, min_col_w)
    total_w = col_w * num_cols + (num_cols - 1) * col_gap
    start_x = MARGIN + (content_w - total_w) / 2
    wordlist_h = num_rows * row_h

    # Grid cell size: fit both the page width AND the remaining page height
    # (title + grid + word list must all fit above the bottom margin — on a
    # square/short trim size, width alone is not the limiting dimension).
    grid_size = len(grid)
    grid_top = MARGIN + TITLE_H + GAP
    max_h_for_grid = (page_h - MARGIN) - grid_top - GAP * 2 - wordlist_h
    cell = min(content_w / grid_size, max(0.1, max_h_for_grid) / grid_size)
    grid_x0 = MARGIN + (content_w - grid_size * cell) / 2

    # Border frame hugging just the letter grid — not the title or word list
    # below it (matches the reference layout).
    border_pad = 0.08
    pdf.set_draw_color(*text_color)
    pdf.set_line_width(0.02)
    pdf.rect(grid_x0 - border_pad, grid_top - border_pad,
              grid_size * cell + 2 * border_pad, grid_size * cell + 2 * border_pad, "D")

    if show_solution:
        highlight = tint_toward_white(primary, 0.6)
        pdf.set_fill_color(*highlight)
        for cells in placements.values():
            for (r, c) in cells:
                x = grid_x0 + c * cell
                y = grid_top + r * cell
                pdf.rect(x, y, cell, cell, "F")

    # Plain letters, no per-cell grid lines (matches the reference layout)
    font_size = max(8, min(20, cell * 45))
    pdf.set_font("Helvetica", "B", font_size)
    pdf.set_text_color(*text_color)
    for r in range(grid_size):
        for c in range(grid_size):
            x = grid_x0 + c * cell
            y = grid_top + r * cell
            pdf.set_xy(x, y + cell * 0.2)
            pdf.cell(cell, cell * 0.6, grid[r][c], align="C")

    # Word bank: alphabetical, filled column-by-column (top-to-bottom, then next column)
    list_top = grid_top + grid_size * cell + GAP * 2
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*text_color)
    for i, word in enumerate(words_sorted):
        col, row = divmod(i, num_rows)
        x = start_x + col * (col_w + col_gap)
        y = list_top + row * row_h
        pdf.set_xy(x, y)
        pdf.cell(col_w, row_h, word, align="C")


# ---------- Assembler ----------

def build_activity_pdf(page_w, page_h, theme,
                        include_cover, cover_title, cover_photo, photo_fill,
                        ws_word_bank, ws_num_puzzles, ws_words_per_puzzle, ws_grid_size, ws_hard_mode,
                        show_answers, ws_start_number=1):
    pdf = FPDF(unit="in", format=(page_w, page_h))
    pdf.set_auto_page_break(False)
    primary = theme["primary"]

    if include_cover:
        pdf.add_page()
        if cover_photo is not None:
            # No title band drawn on top — the AI-generated cover image (via the
            # prompt above) already has the title designed into the artwork itself.
            pil_img, draw_w, draw_h = prepare_photo(cover_photo, page_w, page_h, photo_fill)
            offset_x = (page_w - draw_w) / 2
            offset_y = (page_h - draw_h) / 2
            pdf.image(pil_img, x=offset_x, y=offset_y, w=draw_w, h=draw_h)
        elif cover_title:
            # Plain white background, black text — same reasoning as the
            # ANSWER KEY page: a full black fill is heavy on toner and prone
            # to streaking on print-on-demand presses.
            box_w = min(5.0, page_w - 1.0)
            line_h = 0.5
            pdf.set_font("Helvetica", "B", 24 if page_w < 7 else 28)
            # Box height must follow how many lines the title actually wraps
            # to — a long theme name (e.g. "Space & Astronauts") wraps to 3
            # lines, which overflowed a fixed 1.4in box and got cut by the border.
            wrapped = pdf.multi_cell(box_w - 0.4, line_h, cover_title, align="C", dry_run=True, output="LINES")
            box_h = max(1.4, len(wrapped) * line_h + 0.4)
            box_x = (page_w - box_w) / 2
            box_y = (page_h - box_h) / 2
            pdf.set_draw_color(*primary)
            pdf.set_line_width(0.03)
            pdf.rect(box_x, box_y, box_w, box_h, "D")
            pdf.set_text_color(*primary)
            pdf.set_xy(box_x + 0.2, box_y + (box_h - len(wrapped) * line_h) / 2)
            pdf.multi_cell(box_w - 0.4, line_h, cover_title, align="C")

    bank = [w.strip() for w in ws_word_bank.replace(",", "\n").splitlines() if w.strip()]
    ws_puzzles = []
    for i in range(ws_num_puzzles):
        pool = bank if len(bank) <= ws_words_per_puzzle else random.sample(bank, ws_words_per_puzzle)
        grid, placements, skipped = generate_word_search(pool, ws_grid_size, ws_hard_mode)
        used_words = sorted({w.strip().upper().replace(" ", "") for w in pool} & set(placements.keys()))
        ws_puzzles.append((grid, used_words, placements))
        draw_word_search_page(pdf, page_w, page_h, theme, f"PUZZLE {i + ws_start_number}", grid, used_words, False, {})

    if show_answers and ws_puzzles:
        pdf.add_page()
        # Plain white page with a bordered banner instead of a full black fill —
        # a solid black page is heavy on toner and prone to streaking/uneven
        # coverage on print-on-demand presses, and breaks the all-white look
        # of the rest of the book for no real benefit.
        box_w, box_h = min(4.0, page_w - 1.0), 1.0
        box_x = (page_w - box_w) / 2
        box_y = (page_h - box_h) / 2
        pdf.set_draw_color(*primary)
        pdf.set_line_width(0.03)
        pdf.rect(box_x, box_y, box_w, box_h, "D")
        pdf.set_text_color(*primary)
        pdf.set_font("Helvetica", "B", 28 if page_w < 7 else 34)
        pdf.set_xy(box_x, box_y + box_h / 2 - 0.3)
        pdf.cell(box_w, 0.6, "ANSWER KEY", align="C")

        for i, (grid, used_words, placements) in enumerate(ws_puzzles):
            draw_word_search_page(pdf, page_w, page_h, theme, f"PUZZLE {i + ws_start_number} - ANSWER", grid, used_words, True, placements)

    pdf_bytes = pdf.output()
    return BytesIO(bytes(pdf_bytes))


if check_password():
    st.markdown('<div class="kdp-card">', unsafe_allow_html=True)
    st.title("🧩 KDPEasy Activity Creator")
    st.caption("Create a print-ready Word Search activity book for KDP in seconds.")

    col1, col2 = st.columns(2)
    with col1:
        page_size_label = st.selectbox("Page size", list(PAGE_SIZES.keys()))
    with col2:
        orientation = st.radio("Orientation", ["Portrait", "Landscape"], index=0, horizontal=True)

    theme = THEME
    page_w, page_h = PAGE_SIZES[page_size_label]
    if orientation == "Landscape":
        page_w, page_h = page_h, page_w

    theme_choice = st.selectbox(
        "Word theme", ["Custom (type your own)"] + list(WORD_THEMES.keys()), index=1,
    )

    include_cover = st.checkbox("Include a cover page", value=True)
    cover_title = ""
    cover_photo = None
    photo_fill = False
    if include_cover:
        cover_title = f"{theme_choice.upper()} WORD SEARCH" if theme_choice in WORD_THEMES else "WORD SEARCH PUZZLES"

        with st.expander("Need cover art? Generate a free AI image prompt"):
            cover_prompt = build_cover_prompt(cover_title, theme_choice, page_w, page_h)
            st.caption(
                "Copy this prompt into ChatGPT (or another AI image tool), ask it to generate the image, "
                "then download that image and upload it below as your cover photo."
            )
            st.code(cover_prompt, language=None)

        cover_photo = st.file_uploader("Cover photo (optional, fills the whole cover page)", type=["png", "jpg", "jpeg"], key="cover_photo")
        if cover_photo is not None:
            fit_choice = st.radio(
                "Cover photo style",
                ["Fit — show the full photo, may add white bars (recommended for portrait photos)",
                 "Fill — crop to fill the page, no white bars (best for landscape/square photos)"],
                index=0,
            )
            photo_fill = fit_choice.startswith("Fill")
            cover_prev_img, _, _ = prepare_photo(cover_photo, page_w, page_h, photo_fill)
            st.image(cover_prev_img, caption="Cover photo preview", width=220)

    show_answers = st.checkbox("Include an answer key section at the end", value=True)

    st.markdown("### Word Search settings")
    st.caption(f"Using word theme: **{theme_choice}** (change it above, near Page size)")
    default_words = "\n".join(WORD_THEMES[theme_choice]) if theme_choice in WORD_THEMES else ""
    ws_word_bank = st.text_area(
        "Word bank (auto-filled from the theme above — feel free to add, remove, or edit)",
        value=default_words, height=100, key=f"wordbank_{theme_choice}",
        placeholder="LION\nTIGER\nELEPHANT\nGIRAFFE\nZEBRA",
    )
    wc1, wc2, wc3, wc4 = st.columns(4)
    with wc1:
        ws_num_puzzles = st.number_input("Number of puzzles", min_value=1, max_value=20, value=3)
    with wc2:
        ws_words_per_puzzle = st.number_input("Words per puzzle", min_value=5, max_value=20, value=10)
    with wc3:
        ws_grid_size = st.selectbox("Grid size", [12, 15, 18], index=1)
    with wc4:
        ws_start_number = st.number_input(
            "Start numbering at",
            min_value=1, max_value=999, value=1,
            help="Use this to combine puzzles from different batches into one book without renumbering by hand.",
        )
    ws_hard_mode = st.checkbox("Harder mode (backwards + diagonal words)", value=False)

    bank_preview = [w.strip() for w in ws_word_bank.replace(",", "\n").splitlines() if w.strip()]
    if not bank_preview:
        st.warning("Add at least one word to the word bank to generate a puzzle.")

    export_png = st.checkbox("Also export as PNG images (zipped, 300 DPI)", value=False)

    if st.button("Generate Activity Book PDF"):
        if not bank_preview:
            st.error("Please add at least one word to the word bank above before generating.")
        else:
            pdf_buf = build_activity_pdf(
                page_w, page_h, theme,
                include_cover, cover_title, cover_photo, photo_fill,
                ws_word_bank, int(ws_num_puzzles), int(ws_words_per_puzzle), int(ws_grid_size), ws_hard_mode,
                show_answers, int(ws_start_number),
            )
            pdf_bytes = pdf_buf.getvalue()
            st.success("Your activity book is ready! Here's a preview before you download:")

            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            preview_count = min(2, doc.page_count)
            preview_cols = st.columns(preview_count)
            for i in range(preview_count):
                pix = doc[i].get_pixmap(dpi=110)
                preview_cols[i].image(pix.tobytes("png"), caption=f"Page {i + 1}", use_container_width=True)

            st.download_button(
                "⬇️ Download Activity Book PDF",
                data=pdf_bytes,
                file_name="KDPEasy_Word_Search_Book.pdf",
                mime="application/pdf",
            )

            if export_png:
                zip_buf = BytesIO()
                with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    for i in range(doc.page_count):
                        pix = doc[i].get_pixmap(dpi=300)
                        zf.writestr(f"{i + 1:04d}.png", pix.tobytes("png"))
                zip_buf.seek(0)
                st.download_button(
                    "⬇️ Download PNG Images (ZIP, 300 DPI)",
                    data=zip_buf,
                    file_name="KDPEasy_Word_Search_Book_PNG.zip",
                    mime="application/zip",
                )

            doc.close()
    st.markdown('</div>', unsafe_allow_html=True)
