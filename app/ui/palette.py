from dataclasses import dataclass

FONT_FAMILY = "Inter, system-ui, sans-serif"


@dataclass(frozen=True)
class Palette:
    ink: str
    inverse_text: str
    text: str
    muted: str
    band: str
    page: str
    card: str
    card_muted: str
    border: str
    secondary_bar: str
    gauge_track: str
    gain: str
    loss: str
    warning: str
    categories: tuple[str, ...]
    other_category: str


LIGHT = Palette(
    ink="#1F1F1F",
    inverse_text="#F6F7ED",
    text="#111111",
    muted="#6B6B6B",
    band="#F6F7ED",
    page="#FFFFFF",
    card="#FFFFFF",
    card_muted="#F4F4F4",
    border="#D3D3D3",
    secondary_bar="#82827D",
    gauge_track="#C7C8C0",
    gain="#2E7D4F",
    loss="#C0392B",
    warning="#9A5B00",
    categories=("#1F1F1F", "#6B7A3A", "#A07C3F", "#4F7390", "#A65E4E", "#6E5A8C", "#3F7F7A"),
    other_category="#8A8A82",
)

DARK = Palette(
    ink="#F6F7ED",
    inverse_text="#1F1F1F",
    text="#F2F2F2",
    muted="#A3A3A3",
    band="#1C1D17",
    page="#121212",
    card="#1A1A1A",
    card_muted="#242424",
    border="#3A3A3A",
    secondary_bar="#6B6B66",
    gauge_track="#3A3A35",
    gain="#6FCF97",
    loss="#F28B82",
    warning="#F2B84B",
    categories=("#F6F7ED", "#A9B87A", "#D9B77A", "#8FB0CC", "#D9907F", "#A994C8", "#7FBFB8"),
    other_category="#8A8A82",
)
