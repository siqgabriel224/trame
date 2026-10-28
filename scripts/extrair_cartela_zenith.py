"""Extrai amostras aproximadas dos códigos lisos da cartela digital Zenith 25.
As posições e códigos foram conferidos visualmente nas páginas 2, 3 e 4.
"""

import argparse
import colorsys
import hashlib
import json
import statistics
from pathlib import Path
from PIL import Image

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "source", type=Path, help="Pasta com cartela.pdf e pagina-2.png a pagina-4.png (140 dpi)"
)
source = parser.parse_args().source
columns = [
    "E1451 BCA NAT 2029 2030 2160 2280 2314 2058 2193 2051 2008 2297 2033 2049 2158 3244 2032 2240 2219 2106 9099",
    "2103 2057 2122 2084 2116 2044 2095 2195 2052 2037 2294 2291 2299 2269 2130 2213 2081 7129 2161 2162 2163 2164",
    "2123 3046 2215 2216 2099 2165 2149 2007 2150 2208 3066 2066 2054 2009 2209 3255 2171 2172 9078 2001 2002 3209",
    "3254 2079 3206 2117 2003 2104 2100 2090 2196 2151 2071 3249 2110 2304 2005 2006 2026 2153 2087 8792 2169 9010",
    "2170 2011 2012 2223 2185 2109 2256 2811 2276 2059 2091 2277 9014 2184 2183 8830 2803 2108 9804 2166 2013 2086",
    "2218 2118 2146 3147 2138 3272 2055 2293 2134 2133 2231 2020 9020 2142 2021 9802 3102 2141 2121 3056 2024 1185",
    "9056 1406 2227 2127 3344 1407 2017 2126 2023 2323 2061 2419 2259 2284 3250 3218 2217 2015 2065 2145 2072 2272",
    "2018 2242 2092 2093 2175 2206 2154 2285 2307 2266 2048 2237 2148 2070 2177 2290 2309 2078 2069 2250 2124 2067",
    "2060 3303 3120 2050 9102 2226 2181 3118 2232 2075 2275 2028 3028 2228 9817 3180 2063 2025 3318 2111 2107 3246",
    "2990 2114 2120 2077 2203 2204 2080 2205 2039 2289 2053 2238 2264 2221 2180 2344 2083 2186 2319 2128 2088 5688",
    "2042 3273 2034 2849 2035 2258 3270 2036 2274 2230 2311 2062 2306 2302 2265 2295 2068 2073 2041 3275 2043 2244",
    "2282 2144 2074 2395 3198 0853 2298 3040 2840 8800 2200 2190 2191 2113 2194 2187 2255 2806 2389 2096 2045 2292",
    "2076 2253 2317 2316 2152 2301 2064 2251 2260 2022 2135 2016 2155 2247 2046 2350 2047 2082 8822 8846 2254 PTA",
]
assert all(len(c.split()) == 22 for c in columns)
assert len({c for col in columns for c in col.split()}) == 286
# Central areas of the actual thread photographs, avoiding labels, borders and gaps.
coords = (
    [(2, x, 294, 53.7) for x in [245, 435, 625, 820, 1009]]
    + [(3, x, 290, 53.6) for x in [245, 435, 630, 825, 1017]]
    + [(4, x, 295, 54.5) for x in [231, 426, 620]]
)


def family(rgb, col, row):
    if col in (5, 6):
        return "Azul"
    if col == 8:
        return "Verde"
    if col == 7 and row >= 18:
        return "Verde"
    if col == 7:
        return "Azul"
    h, s, v = colorsys.rgb_to_hsv(*(n / 255 for n in rgb))
    h *= 360
    if v < 0.12:
        return "Preto"
    if s < 0.12:
        return "Branco" if v > 0.82 else "Cinza"
    if s < 0.22 and v > 0.55:
        return "Bege"
    if h < 16 or h >= 345:
        return "Rosa" if v > 0.68 and s < 0.55 else "Vermelho"
    if h < 42:
        return "Bege" if v > 0.65 and s < 0.4 else "Marrom" if v < 0.65 else "Laranja"
    if h < 70:
        return "Amarelo" if v > 0.6 else "Marrom"
    if h < 174:
        return "Verde"
    if h < 260:
        return "Azul"
    if h < 300:
        return "Roxo"
    return "Rosa"


colors = {}
for col, (codes, (page, x, y0, pitch)) in enumerate(zip(columns, coords)):
    im = Image.open(source / f"pagina-{page}.png").convert("RGB")
    for row, code in enumerate(codes.split()):
        y = round(y0 + pitch * row)
        patch = list(im.crop((x - 15, y - 7, x + 15, y + 7)).getdata())
        rgb = tuple(round(statistics.median(p[k] for p in patch)) for k in range(3))
        colors[code] = {
            "hex": "#" + "".join(f"{n:02x}" for n in rgb),
            "family": family(rgb, col, row),
            "position": f"{col + 1}{chr(65 + row)}",
        }
result = {
    "brand": "Zenith",
    "version": "cartela-25-digital-v1",
    "approximate": True,
    "coverage": "286 códigos lisos das colunas 1 a 13; metálicas e multicor não incluídas",
    "sourceUrl": "https://cdn.sistemawbuy.com.br/arquivos/add7561ecda3ba37f1a384cd925d3d94/catalogos/cartela-de-cores-zenith-linhanyl-68f108049b039.pdf",
    "sourceSha256": hashlib.sha256((source / "cartela.pdf").read_bytes()).hexdigest(),
    "method": "Mediana RGB de uma área central de cada amostra fotografada; renderização a 140 dpi. Grupos de filtro aproximados e editáveis. Não são valores oficiais RGB.",
    "aliases": {"853": "0853"},
    "colors": colors,
}
(root / "web/zenith-colors.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(
    json.dumps(
        {code: colors[code] for code in ["2028", "2075", "2228", "BCA", "PTA"]}, ensure_ascii=False
    )
)
