"""M10 studio features: palette control, black & white / grayscale, background removal, cutout layout, speckle filter,
and the PDF / EPS / DXF exports."""
import io
import re
import time
import zipfile

import pytest
from PIL import Image, ImageDraw

from pngsvg import options_for, vectorize
from pngsvg.export import convert, parse_path, parse_svg
from pngsvg.pathdata import compact_path

HEX = re.compile(r'(?:fill|stroke|stop-color)="(#[0-9A-F]{6})"')


def picture(size=(200, 150), background=(240, 244, 250, 255)) -> Image.Image:
    img = Image.new('RGBA', size, background)
    d = ImageDraw.Draw(img)
    d.ellipse((20, 15, 110, 105), fill=(37, 99, 235, 255), outline=(15, 23, 42, 255), width=3)
    d.rectangle((95, 55, 180, 130), fill=(245, 158, 11, 255))
    d.ellipse((125, 75, 155, 105), fill=(220, 38, 38, 255))    # a hole in the orange square
    for x in range(30, 190, 37):                                  # specks
        d.rectangle((x, 138, x + 2, 140), fill=(16, 185, 129, 255))
    return img


def colors(svg: str) -> set[str]:
    return set(HEX.findall(svg))


def test_max_colors_limits_the_palette_and_reports_it():
    r = vectorize(picture(), options_for('cartoon', max_colors=4))
    assert len(colors(r.svg)) <= 4 and 'Gradient' not in r.svg
    assert set(r.palette) == colors(r.svg)


def test_fixed_palette_and_black_and_white():
    pal = ('#112233', '#F0F0F0', '#E0A000')
    r = vectorize(picture(), options_for('cartoon', palette=pal))
    assert colors(r.svg) <= set(pal)
    bw = vectorize(picture(), options_for('logo', color_mode='bw'))
    assert colors(bw.svg) <= {'#000000', '#FFFFFF'}
    gray = vectorize(picture(), options_for('cartoon', color_mode='grayscale'))
    assert all(c[1:3] == c[3:5] == c[5:7] for c in colors(gray.svg))


def test_remove_background_by_border_and_by_transparency():
    plain = vectorize(picture())
    nobg = vectorize(picture(), options_for('cartoon', remove_bg=True))
    assert '<rect' in plain.svg and '<rect' not in nobg.svg
    assert '#F0F4FA' not in nobg.svg.upper() and nobg.regions < plain.regions
    clear = vectorize(picture(background=(0, 0, 0, 0)), options_for('cartoon', remove_bg=True))
    assert '<rect' not in clear.svg and '#FFFFFF' not in clear.svg, 'transparent pixels are not painted white'


def test_cutout_cuts_holes_instead_of_stacking():
    r = vectorize(picture(), options_for('flat', layout='cutout', gradients=False))
    assert 'fill-rule="evenodd"' in r.svg and '<rect' not in r.svg
    orange = next(p for p in parse_svg(r.svg).shapes if p.fill == (245 / 255, 158 / 255, 11 / 255))
    assert len(orange.paths) >= 2, 'the red circle is cut out of the orange square'


def test_speckle_filter_removes_small_spots():
    from pngsvg_app.jobs import build_options
    keep = vectorize(picture(), build_options('cartoon', {'speckle': 0}, 'a'))
    clean = vectorize(picture(), build_options('cartoon', {'speckle': 40}, 'a'))
    assert clean.regions < keep.regions


def test_path_parser_reads_compact_relative_paths():
    d = 'M10 20L30 20C40 20 50 30 50 40Q50 60 30 60ZM100 100L110 100L110 110Z'
    paths = parse_path(compact_path(d, decimals=2))
    assert [p[0] for p in paths] == [(10, 20), (100, 100)]
    assert paths[0][1][0] == ('L', (30, 20))
    assert paths[0][1][1] == ('C', (40, 20), (50, 30), (50, 40))
    assert paths[0][1][2][3] == (30, 60), 'quadratic segments become cubic ones'


@pytest.fixture(scope='module')
def result_svg() -> str:
    return vectorize(picture()).svg


def test_pdf_is_well_formed(result_svg):
    pdf = convert(result_svg, 'pdf')
    assert pdf.startswith(b'%PDF-1.4') and pdf.rstrip().endswith(b'%%EOF')
    xref = int(re.search(rb'startxref\n(\d+)', pdf).group(1))
    assert pdf[xref:xref + 4] == b'xref'
    offsets = [int(o) for o in re.findall(rb'(\d{10}) 00000 n', pdf)]
    for i, off in enumerate(offsets, 1):
        assert pdf[off:].startswith(f'{i} 0 obj'.encode()), 'xref offsets point at their objects'
    assert b'/MediaBox [0 0 200 150]' in pdf
    assert pdf.count(b'/ShadingType') == result_svg.count('Gradient id=')


def test_eps_and_dxf(result_svg):
    eps = convert(result_svg, 'eps').decode('ascii')
    assert eps.startswith('%!PS-Adobe-3.0 EPSF-3.0') and '%%BoundingBox: 0 0 200 150' in eps
    assert eps.count('shfill') == result_svg.count('Gradient id=')
    dxf = convert(result_svg, 'dxf').decode('ascii')
    assert 'AC1009' in dxf and dxf.rstrip().endswith('EOF')
    assert dxf.count('\nPOLYLINE\n') >= len(parse_svg(result_svg).shapes) and '\nOUTLINE\n' in dxf
    with pytest.raises(ValueError):
        convert(result_svg, 'jpg')


# ---------------------------------------------------------------------------------------------------- service API

pytest.importorskip('fastapi')
from fastapi.testclient import TestClient  # noqa: E402

from pngsvg_app import server  # noqa: E402
from pngsvg_app.jobs import JobManager  # noqa: E402

H = {'X-Token': 't'}


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    jobs = JobManager(workers=1)
    jobs.start()
    app = server.create_app(jobs, 't', {'testserver'}, static_dir=tmp_path_factory.mktemp('static'))
    with TestClient(app) as c:
        yield c
    jobs.shutdown()


def png_bytes() -> bytes:
    buf = io.BytesIO()
    picture().save(buf, 'PNG')
    return buf.getvalue()


def done(client, jid: str) -> dict:
    end = time.time() + 120
    while time.time() < end:
        j = client.get(f'/api/jobs/{jid}', headers=H).json()
        if j['status'] in ('done', 'error'):
            return j
        time.sleep(0.1)
    raise AssertionError('job did not finish')


def test_studio_options_validated_and_applied(client):
    for bad in ('{"palette":["red"]}', '{"max_colors":1}', '{"color_mode":"sepia"}', '{"layout":"x"}',
                '{"seam":3}'):
        assert client.post(f'/api/jobs?name=a.png&options={bad}', content=png_bytes(), headers=H).status_code == 422
    r = client.post('/api/jobs?name=a.png&options={"max_colors":3,"remove_bg":true}', content=png_bytes(), headers=H)
    j = done(client, r.json()['id'])
    assert j['status'] == 'done' and 1 <= len(j['stats']['palette']) <= 3
    presets = client.get('/api/presets', headers=H).json()
    assert {'speckle', 'seam'} <= {o['name'] for o in presets['options']}


def test_export_formats(client):
    jid = client.post('/api/jobs?name=Kucing lucu.png', content=png_bytes(), headers=H).json()['id']
    done(client, jid)
    for fmt, magic, mime in (('pdf', b'%PDF', 'application/pdf'), ('eps', b'%!PS', 'application/postscript'),
                             ('dxf', b'0\nSECTION', 'image/vnd.dxf'), ('svg', b'<svg', 'image/svg+xml')):
        r = client.get(f'/api/jobs/{jid}/export?format={fmt}', headers=H)
        assert r.status_code == 200 and r.content.startswith(magic) and r.headers['content-type'].startswith(mime)
        assert f'Kucing lucu.{fmt}' in r.headers['content-disposition']
    assert client.get(f'/api/jobs/{jid}/export?format=png', headers=H).status_code == 422
    z = client.get(f'/api/export.zip?ids={jid},{jid}&format=pdf', headers=H)
    names = zipfile.ZipFile(io.BytesIO(z.content)).namelist()
    assert names == ['Kucing lucu.pdf', 'Kucing lucu-2.pdf']


# ---------------------------------------------------------------------------------------------- profiles and CLI

def test_profile_round_trip_and_validation(tmp_path):
    from pngsvg.profile import ProfileError, dump, load, parse
    text = dump('logo', {'max_colors': 4, 'palette': ['#aabbcc'], 'remove_bg': True, 'seam': None}, 'Brand')
    path = tmp_path / 'brand.pngsvg-profile.json'
    path.write_text(text, encoding='utf-8')
    assert load(path) == ('logo', {'max_colors': 4, 'palette': ['#AABBCC'], 'remove_bg': True}, 'Brand')
    for bad in ({'format': 'x', 'version': 1}, {'format': 'pngsvg-profile', 'version': 2},
                {'format': 'pngsvg-profile', 'version': 1, 'preset': 'nope'},
                {'format': 'pngsvg-profile', 'version': 1, 'options': {'max_colors': 99}},
                {'format': 'pngsvg-profile', 'version': 1, 'options': {'remove_bg': 1}},
                {'format': 'pngsvg-profile', 'version': 1, 'options': {'__class__': 1}},
                {'format': 'pngsvg-profile', 'version': 1, 'options': {'palette': ['red']}}):
        with pytest.raises(ProfileError):
            parse(bad)


def test_cli_profile_and_formats(tmp_path, capsys):
    from pngsvg.cli import main
    src = tmp_path / 'pic.png'
    picture().save(src)
    prof = tmp_path / 'p.pngsvg-profile.json'
    prof.write_text('{"format":"pngsvg-profile","version":1,"preset":"flat","options":{"max_colors":3}}',
                    encoding='utf-8')
    assert main([str(src), '--profile', str(prof), '-j', '1']) == 0
    assert len(colors((tmp_path / 'pic.svg').read_text(encoding='utf-8'))) <= 3
    assert main([str(src), '-o', str(tmp_path / 'out.pdf'), '-j', '1', '--remove-bg']) == 0
    assert (tmp_path / 'out.pdf').read_bytes().startswith(b'%PDF')
    assert main([str(src), str(src), '-o', str(tmp_path / 'many'), '-f', 'dxf', '-j', '1']) == 0
    assert (tmp_path / 'many' / 'pic.dxf').exists()
    with pytest.raises(SystemExit):
        main([str(src), '--palette', 'red,blue'])


def test_profile_check_endpoint(client):
    ok = client.post('/api/profiles/check', headers=H,
                     content=b'{"format":"pngsvg-profile","version":1,"name":"Logo","preset":"logo",'
                             b'"options":{"palette":["#abcdef"],"layout":"cutout"}}')
    assert ok.json() == {'preset': 'logo', 'options': {'palette': ['#ABCDEF'], 'layout': 'cutout'}, 'name': 'Logo'}
    assert client.post('/api/profiles/check', headers=H, content=b'{nope').json()['detail'] == 'not valid JSON'
    bad = client.post('/api/profiles/check', headers=H, content=b'{"format":"pngsvg-profile","version":1,'
                                                                  b'"options":{"max_colors":500}}')
    assert bad.status_code == 422 and 'max_colors' in bad.json()['detail']
    assert client.post('/api/profiles/check', content=b'{}').status_code == 401
