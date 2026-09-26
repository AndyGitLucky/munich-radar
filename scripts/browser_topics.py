"""Exercise topic filters across the full dataset, dates, maps and personal actions."""
import copy
import tempfile
import threading
import shutil
from pathlib import Path
from functools import partial
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright
from browser_features import ROOT, QuietHandler, fixtures, launch, configure, settled
from src.build import build


def main():
    data, metadata = fixtures()
    # Only low-ranked events beyond the default five match music; no threshold may hide them.
    events = copy.deepcopy(data[:12])
    for i,event in enumerate(events):
        event.update(category='other',tags=[],description=None,source_name=f'Quelle {i}',location_name='Gasteig HP8')
        if i >= 5:
            event.update(title=f'Jazzkonzert {i}',category='concert',tags=['concert'],relevance_score=10)
    food = dict(events[0],id='f'*20,title='Bauernmarkt mit Livemusik',category='market',tags=['market'],
                start='2026-09-26T09:00:00+02:00',end='2026-09-26T13:00:00+02:00',is_free=True)
    flea = dict(food,id='e'*20,title='Flohmarkt',is_free=False)
    events += [food,flea]
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copytree(build(ROOT),Path(tmp)/'munich-radar')
        with ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=tmp)) as server:
            threading.Thread(target=server.serve_forever,daemon=True).start()
            try:
                with sync_playwright() as p:
                    browser=launch(p); context=browser.new_context(viewport={'width':390,'height':844})
                    page=context.new_page(); configure(page,events,metadata)
                    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                    page.goto(f'http://127.0.0.1:{server.server_port}/munich-radar/');settled(page)
                    assert page.locator('.event-card').count()==5
                    assert not any('Jazz' in t for t in page.locator('.event-card h3').all_text_contents())
                    page.locator('[data-topic=music]').click()
                    assert page.locator('.event-card').count()==5
                    assert all('Jazz' in t for t in page.locator('.event-card h3').all_text_contents())
                    assert '7 passende' in page.locator('#topic-status').inner_text()
                    assert page.locator('[data-topic=music]').get_attribute('aria-pressed')=='true'
                    page.locator('#all-results').click();assert page.locator('.event-card').count()==7
                    page.locator('[data-display=map]').click()
                    page.wait_for_function("document.querySelector('#event-map').dataset.eventCount === '7'")
                    page.locator('[data-view=tomorrow]').click()
                    page.wait_for_function("document.querySelector('#event-map').dataset.eventCount === '1'")
                    page.locator('[data-topic=shopping]').click()
                    page.wait_for_function("document.querySelector('#event-map').dataset.eventCount === '2'")
                    page.locator('[data-topic=food]').click()
                    page.wait_for_function("document.querySelector('#event-map').dataset.eventCount === '1'")
                    page.locator('[data-display=list]').click()
                    assert page.locator('.event-card h3').inner_text()=='Bauernmarkt mit Livemusik'
                    page.locator('[data-filter=free]').click();assert page.locator('.event-card').count()==1
                    page.locator('.event-card [data-save-id]').click()
                    with page.expect_download() as download: page.locator('.event-card [data-calendar-id]').click()
                    assert b'20260926T070000Z' in Path(download.value.path()).read_bytes()
                    page.locator('[data-view=saved]').click();assert page.locator('.event-card').count()==1
                    page.locator('[data-topic=science]').click();assert page.locator('.event-card').count()==0
                    assert 'Keine passenden Wissen' in page.locator('#events').inner_text()
                    # Scientific museums do not automatically count as visual art or food.
                    topics=page.evaluate("() => [...RadarTopics.classify({title:'Vorführung',category:'science',tags:['museum'],source_name:'Deutsches Museum'})]")
                    assert topics==['science']
                    assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
                    page.set_viewport_size({'width':320,'height':700})
                    assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
                    assert not errors,errors
                    browser.close()
                    print('Topic checks passed: full dataset, low scores, dates, multi-topic, non-food markets, map, bookmarks, ICS, mobile.')
            finally: server.shutdown()

if __name__=='__main__':main()
