import streamlit as st
import fitz
import zipfile
import random
from collections import deque
from datetime import date
from fpdf import FPDF
from io import BytesIO
from PIL import Image

st.set_page_config(page_title="KDPEasy Maze Creator", page_icon="🌀", layout="centered")

# Password -> expiry date, or None for permanent access (paying customers).
PASSWORD_EXPIRY = {
    "KDPMAZE2026": None,
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

# Fixed high-contrast look, optimized for black & white KDP interior printing.
THEME = {"primary": (0, 0, 0), "text": (0, 0, 0)}

# Short visual-scene hints used to build a cover-art AI image prompt per theme.
COVER_THEME_HINTS = {
    "Farm Animals": "a cheerful farmyard scene with a cow, pig, chickens, and a red barn under a sunny blue sky",
    "Ocean & Sea Life": "a colorful underwater scene with a dolphin, tropical fish, and a coral reef",
    "Dinosaurs": "friendly cartoon dinosaurs in a lush prehistoric jungle landscape",
    "Space & Astronauts": "a fun outer-space scene with planets, stars, and a cartoon astronaut floating by a rocket",
    "Jungle & Safari": "a lively jungle safari scene with a lion, an elephant, and tropical plants",
    "Halloween": "a fun, not-scary Halloween scene with a friendly pumpkin, a cute ghost, and a haunted house",
    "Fantasy Castle": "a whimsical fantasy scene with a castle, a friendly dragon, and a knight",
    "Robots & Tech": "a playful scene with colorful cartoon robots and gadgets",
    "Under the Sea Pirates": "a fun pirate scene with a treasure chest, a ship, and a parrot",
    "Winter Wonderland": "a cozy winter scene with snow, a snowman, and pine trees",
}


def build_cover_prompt(book_title, theme_choice, page_w, page_h):
    subject = COVER_THEME_HINTS.get(theme_choice, "a fun, colorful puzzle-book theme")
    title_text = book_title.strip() if book_title.strip() else "MAZE"
    orientation = "portrait" if page_h >= page_w else "landscape"
    trim_w = f"{page_w:g}"
    trim_h = f"{page_h:g}"
    return (
        f"Create a vibrant, full-color book cover illustration for a kids' MAZE puzzle book. "
        f"Make it immediately obvious this is a maze / puzzle book - for example, weave a few "
        f"playful winding path lines or a faint maze-corner pattern into the background "
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
    st.title("🌀 KDPEasy Maze Creator")
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


# ---------- Maze ----------

MAZE_DIRS = [("N", 0, -1), ("S", 0, 1), ("E", 1, 0), ("W", -1, 0)]
MAZE_OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E"}
MAZE_SIZES = {"Small (10 x 10)": (10, 10), "Medium (15 x 15)": (15, 15), "Large (20 x 20)": (20, 20)}


def generate_maze(width, height):
    walls = {(x, y): {"N": True, "S": True, "E": True, "W": True} for x in range(width) for y in range(height)}
    visited = {(0, 0)}
    stack = [(0, 0)]
    while stack:
        x, y = stack[-1]
        dirs = MAZE_DIRS[:]
        random.shuffle(dirs)
        moved = False
        for d, dx, dy in dirs:
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in visited:
                walls[(x, y)][d] = False
                walls[(nx, ny)][MAZE_OPPOSITE[d]] = False
                visited.add((nx, ny))
                stack.append((nx, ny))
                moved = True
                break
        if not moved:
            stack.pop()
    walls[(0, 0)]["W"] = False
    walls[(width - 1, height - 1)]["E"] = False
    return walls


def solve_maze(walls, width, height):
    start, end = (0, 0), (width - 1, height - 1)
    queue = deque([start])
    came_from = {start: None}
    while queue:
        cur = queue.popleft()
        if cur == end:
            break
        x, y = cur
        for d, dx, dy in MAZE_DIRS:
            nxt = (x + dx, y + dy)
            if not walls[(x, y)][d] and 0 <= nxt[0] < width and 0 <= nxt[1] < height:
                if nxt not in came_from:
                    came_from[nxt] = cur
                    queue.append(nxt)
    path = []
    cur = end
    while cur is not None:
        path.append(cur)
        cur = came_from.get(cur)
    path.reverse()
    return path


def draw_maze_page(pdf, page_w, page_h, theme, title, walls, width, height, solution_path=None):
    text_color = theme["text"]

    pdf.add_page()
    content_w = page_w - 2 * MARGIN

    # Plain centered title, no colored band (matches the rest of the KDPEasy activity family).
    pdf.set_text_color(*text_color)
    pdf.set_font("Helvetica", "B", 22 if page_w >= 7 else 18)
    pdf.set_xy(MARGIN, MARGIN)
    pdf.cell(content_w, TITLE_H, title, align="C")

    grid_top = MARGIN + TITLE_H + GAP
    max_h_for_grid = (page_h - MARGIN) - grid_top
    cell = min(content_w / width, max(0.1, max_h_for_grid) / height)
    maze_w = cell * width
    maze_h = cell * height
    x0 = MARGIN + (content_w - maze_w) / 2
    y0 = grid_top + (max(0.0, max_h_for_grid - maze_h)) / 2

    pdf.set_draw_color(*text_color)
    pdf.set_line_width(0.025)
    for x in range(width):
        for y in range(height):
            cx = x0 + x * cell
            cy = y0 + y * cell
            w = walls[(x, y)]
            if w["N"]:
                pdf.line(cx, cy, cx + cell, cy)
            if w["S"]:
                pdf.line(cx, cy + cell, cx + cell, cy + cell)
            if w["W"]:
                pdf.line(cx, cy, cx, cy + cell)
            if w["E"]:
                pdf.line(cx + cell, cy, cx + cell, cy + cell)

    if solution_path:
        # Mid-gray, not black — a black solution line is nearly invisible against
        # the black maze walls. Gray reads clearly as "the answer" at a glance.
        pdf.set_draw_color(150, 150, 150)
        pdf.set_line_width(cell * 0.22)
        pts = [(x0 + (x + 0.5) * cell, y0 + (y + 0.5) * cell) for x, y in solution_path]
        for i in range(len(pts) - 1):
            pdf.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
        pdf.set_draw_color(*text_color)
    pdf.set_line_width(0.01)


# ---------- Assembler ----------

def build_maze_pdf(page_w, page_h, theme,
                    include_cover, cover_title, cover_photo, photo_fill,
                    mz_num_mazes, mz_dims, show_answers, mz_start_number=1):
    pdf = FPDF(unit="in", format=(page_w, page_h))
    pdf.set_auto_page_break(False)
    primary = theme["primary"]

    if include_cover:
        pdf.add_page()
        if cover_photo is not None:
            pil_img, draw_w, draw_h = prepare_photo(cover_photo, page_w, page_h, photo_fill)
            offset_x = (page_w - draw_w) / 2
            offset_y = (page_h - draw_h) / 2
            pdf.image(pil_img, x=offset_x, y=offset_y, w=draw_w, h=draw_h)
        elif cover_title:
            box_w, box_h = min(5.0, page_w - 1.0), 1.4
            box_x = (page_w - box_w) / 2
            box_y = (page_h - box_h) / 2
            pdf.set_draw_color(*primary)
            pdf.set_line_width(0.03)
            pdf.rect(box_x, box_y, box_w, box_h, "D")
            pdf.set_text_color(*primary)
            pdf.set_font("Helvetica", "B", 24 if page_w < 7 else 28)
            pdf.set_xy(box_x + 0.2, box_y + 0.2)
            pdf.multi_cell(box_w - 0.4, 0.5, cover_title, align="C")

    width, height = mz_dims
    mz_puzzles = []
    for i in range(mz_num_mazes):
        walls = generate_maze(width, height)
        path = solve_maze(walls, width, height)
        mz_puzzles.append(walls)
        draw_maze_page(pdf, page_w, page_h, theme, f"MAZE {i + mz_start_number}", walls, width, height, None)

    if show_answers and mz_puzzles:
        pdf.add_page()
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

        for i, walls in enumerate(mz_puzzles):
            path = solve_maze(walls, width, height)
            draw_maze_page(pdf, page_w, page_h, theme, f"MAZE {i + mz_start_number} - ANSWER", walls, width, height, path)

    pdf_bytes = pdf.output()
    return BytesIO(bytes(pdf_bytes))


if check_password():
    st.markdown('<div class="kdp-card">', unsafe_allow_html=True)
    st.title("🌀 KDPEasy Maze Creator")
    st.caption("Create a print-ready Maze activity book for KDP in seconds.")

    col1, col2 = st.columns(2)
    with col1:
        page_size_label = st.selectbox("Page size", list(PAGE_SIZES.keys()))
    with col2:
        orientation = st.radio("Orientation", ["Portrait", "Landscape"], index=0, horizontal=True)

    theme = THEME
    page_w, page_h = PAGE_SIZES[page_size_label]
    if orientation == "Landscape":
        page_w, page_h = page_h, page_w

    theme_choice = st.selectbox("Cover theme", list(COVER_THEME_HINTS.keys()), index=0)

    include_cover = st.checkbox("Include a cover page", value=True)
    cover_title = ""
    cover_photo = None
    photo_fill = False
    if include_cover:
        cover_title = f"{theme_choice.upper()} MAZE"

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

    st.markdown("### Maze settings")
    mc1, mc2, mc3 = st.columns(3)
    with mc1:
        mz_num_mazes = st.number_input("Number of mazes", min_value=1, max_value=20, value=5)
    with mc2:
        mz_size_label = st.selectbox("Maze size", list(MAZE_SIZES.keys()), index=1)
    with mc3:
        mz_start_number = st.number_input(
            "Start numbering at",
            min_value=1, max_value=999, value=1,
            help="Use this to combine mazes from different batches into one book without renumbering by hand.",
        )
    mz_dims = MAZE_SIZES[mz_size_label]

    export_png = st.checkbox("Also export as PNG images (zipped, 300 DPI)", value=False)

    if st.button("Generate Maze Book PDF"):
        pdf_buf = build_maze_pdf(
            page_w, page_h, theme,
            include_cover, cover_title, cover_photo, photo_fill,
            int(mz_num_mazes), mz_dims, show_answers, int(mz_start_number),
        )
        pdf_bytes = pdf_buf.getvalue()
        st.success("Your maze book is ready! Here's a preview before you download:")

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        preview_count = min(2, doc.page_count)
        preview_cols = st.columns(preview_count)
        for i in range(preview_count):
            pix = doc[i].get_pixmap(dpi=110)
            preview_cols[i].image(pix.tobytes("png"), caption=f"Page {i + 1}", use_container_width=True)

        st.download_button(
            "⬇️ Download Maze Book PDF",
            data=pdf_bytes,
            file_name="KDPEasy_Maze_Book.pdf",
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
                file_name="KDPEasy_Maze_Book_PNG.zip",
                mime="application/zip",
            )

        doc.close()
    st.markdown('</div>', unsafe_allow_html=True)
