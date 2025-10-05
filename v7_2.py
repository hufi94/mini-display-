 # left cyan accents
        left_inner_x = TL.left() + 60
        num_traces = 2
        gap_top = TL.bottom() + 4
        gap_bot = BL.top() - 4
        gap_height = gap_bot - gap_top
        spacing = max(1, gap_height // (num_traces + 1))
        for i in range(num_traces):
            y1 = gap_top + (i + 1) * spacing
            y2 = gap_bot - (i + 1) * spacing
            mid_y = (y1 + y2) // 2
            jog = -40 if i % 2 == 0 else 40
            path = ortho_path([(left_inner_x, y1), (left_inner_x + jog, mid_y), (left_inner_x, y2)])
            width = CORE if i % 2 == 0 else max(1, CORE // 2)
            neon_stroke(p, path, CYAN, width)