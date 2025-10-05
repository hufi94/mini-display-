def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # ──────── Core neon trace layout ────────
        TL, TR, BL, BR = (
            self.top_left.geometry(),
            self.top_right.geometry(),
            self.bottom_left.geometry(),
            self.bottom_right.geometry(),
        )

        mid_x = (TL.right() + TR.left()) // 2
        top_bus_y, bot_bus_y = TL.center().y(), BL.center().y()
        tl_r, tr_l = (TL.right() + PADDING, TL.center().y()), (TR.left() - PADDING, TR.center().y())
        bl_r, br_l = (BL.right() + PADDING, BL.center().y()), (BR.left() - PADDING, BR.center().y())

        # Buses
        for o in BUS_OFFS:
            y = top_bus_y + o
            path = ortho_path([(tl_r[0], y), (mid_x - 28, y), (mid_x - 28, y + 12),
                               (mid_x - 12, y + 12), (mid_x - 12, y), (tr_l[0], y)])
            neon_stroke(p, path, CYAN, CORE)
        for o in BUS_OFFS:
            y = bot_bus_y + o
            path = ortho_path([(bl_r[0], y), (mid_x + 28, y), (mid_x + 28, y - 12),
                               (mid_x + 12, y - 12), (mid_x + 12, y), (br_l[0], y)])
            neon_stroke(p, path, CYAN, CORE)

        # Spines
        mid_gap_top = TL.bottom() + PADDING - 40
        mid_gap_bot = BR.top() - PADDING + 40
        for o in SPINE_OFFS:
            x = mid_x + o
            path = ortho_path([
                (x, mid_gap_top),
                (x, (mid_gap_top + mid_gap_bot) // 2 - 27),
                (x + (30 if o < 10 else 30), (mid_gap_top + mid_gap_bot) // 2 - 2),
                (x, (mid_gap_top + mid_gap_bot) // 2 + 27),
                (x, mid_gap_bot),
            ])
            neon_stroke(p, path, CYAN, CORE // 3)

        # Right cyan motherboard style lines
        right_x = TR.right() - 60
        gap_top_r, gap_bot_r = TR.bottom(), BR.top()
        center_y_r = (gap_top_r + gap_bot_r) // 2
        path = ortho_path([(right_x, gap_top_r), (right_x, gap_bot_r)])
        neon_stroke(p, path, CYAN, CORE)
        for o in BRANCH_OFFSETS:
            y = center_y_r + o
            if gap_top_r < y < gap_bot_r:
                path = ortho_path([(right_x, y), (right_x - 80, y)])
                neon_stroke(p, path, CYAN, CORE // 2)
                neon_dot(p, QPointF(right_x - 80, y), CYAN, 5)

        # Bottom pink glowing base lines
        base_y = BR.bottom() + 18
        for w in (1, 3):
            path = ortho_path([(TL.left() + 20, base_y + 6 * w),
                               (TR.right() - 40, base_y + 6 * w)])
            neon_stroke(p, path, PINK, w)

        p.end()