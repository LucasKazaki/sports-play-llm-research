// Local UI verification. Set NODE_PATH to the bundled Playwright package root.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const out=process.argv[2];
if(!out)throw Error('Supply a screenshot/output directory.');
fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHESS_QA_BROWSER?{executablePath:process.env.CHESS_QA_BROWSER}:{})});
 const context=await browser.newContext({viewport:{width:1360,height:1040},colorScheme:'light',reducedMotion:'reduce'});
 const page=await context.newPage(), errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 async function idle(){await page.waitForFunction(()=>!document.getElementById('load').disabled && document.querySelectorAll('.square').length===64,{timeout:120000});}
 await page.goto('http://127.0.0.1:8793/');await idle();
 assert.match(await page.locator('#engine-state').innerText(),/Stockfish/);
 assert.match(await page.locator('#model-result').innerText(),/raw moves legally replayed/);
 await page.screenshot({path:path.join(out,'chess-tutor-desktop.png'),fullPage:true});
 const initial=await page.locator('#turn').innerText();
 await page.getByRole('button',{name:'Flip board orientation'}).click();
 assert.equal(await page.locator('.square').first().getAttribute('data-square'),'h1');
 assert.equal(await page.locator('#turn').innerText(),initial);
 await page.getByRole('button',{name:'Flip board orientation'}).click();
 // Keyboard roving focus and board play; this is a legal move from the opening.
 await page.locator('[data-square="d2"]').focus();await page.keyboard.press('Enter');
 assert.equal(await page.locator('[data-square="d2"]').getAttribute('aria-selected'),'true');
 await page.locator('[data-square="d3"]').click();await idle();
 assert.match(await page.locator('#turn').innerText(),/Black to move/);
 await page.getByRole('button',{name:'Previous position'}).click();await idle();
 assert.match(await page.locator('#turn').innerText(),/White to move/);
 // A failed navigation cannot move the history marker or alter export state.
 const moveCountBefore=await page.locator('#move-count').innerText();
 await page.route('**/api/analyze',route=>route.abort(),{times:1});
 await page.getByRole('button',{name:'Previous position'}).click();await idle();
 assert.equal(await page.locator('#move-count').innerText(),moveCountBefore);
 assert.match(await page.locator('#turn').innerText(),/White to move/);
 // Preview must not replace the analyzed position or model comparison.
 const modelBefore=await page.locator('#model-result').innerText();
 await page.locator('#pv button').first().click();
 assert.match(await page.locator('#turn').innerText(),/preview/);
 assert.equal(await page.locator('#model-result').innerText(),modelBefore);
 await page.getByRole('button',{name:'Return to the analyzed position'}).click();
 assert.doesNotMatch(await page.locator('#turn').innerText(),/preview/);
 // Bad input is visible and preserves the board.
 await page.locator('#position-input').fill('not a chess game');
 await page.getByRole('button',{name:'Load position',exact:true}).click();await idle();
 assert.equal(await page.locator('#input-error').isVisible(),true);
 assert.match(await page.locator('#turn').innerText(),/White to move/);
 // PGN import and navigation.
 await page.locator('#position-input').fill('[Event "<script>window.pgnInjected=true</script>"]\n\n1. d4 d5 2. c4 e6 *');
 await page.getByRole('button',{name:'Load position',exact:true}).click();await idle();
 assert.equal(await page.locator('#timeline button').count(),5);
 assert.equal(await page.evaluate(()=>window.pgnInjected),undefined);
 await page.getByRole('button',{name:'Go to start',exact:true}).click();await idle();
 assert.equal(await page.locator('#move-count').innerText(),'Start position');
 await page.getByRole('button',{name:'Next position'}).click();await idle();
 assert.match(await page.locator('#turn').innerText(),/Black to move/);
 // Automatic repetition draw survives imported-game navigation.
 await page.locator('#position-input').fill('1. Nf3 Nf6 2. Ng1 Ng8 3. Nf3 Nf6 4. Ng1 Ng8 5. Nf3 Nf6 6. Ng1 Ng8 7. Nf3 Nf6 8. Ng1 Ng8 1/2-1/2');
 await page.getByRole('button',{name:'Load position',exact:true}).click();await idle();
 assert.match(await page.locator('#turn').innerText(),/Game over · 1\/2-1\/2/);
 await page.getByRole('button',{name:'Previous position'}).click();await idle();
 assert.doesNotMatch(await page.locator('#turn').innerText(),/Game over/);
 await page.getByRole('button',{name:'Next position'}).click();await idle();
 assert.match(await page.locator('#turn').innerText(),/Game over · 1\/2-1\/2/);
 // Positive deterministic fixture and terminal handling.
 await page.getByRole('button',{name:'Try a mate in one'}).click();await idle();
 assert.equal(await page.locator('#best-move').innerText(),'Qd8#');
 assert.match(await page.locator('#facts').innerText(),/checkmate/);
 await page.locator('[data-square="g5"]').click();await page.locator('[data-square="d8"]').click();await idle();
 assert.match(await page.locator('#turn').innerText(),/Checkmate/);
 assert.equal(await page.locator('#engine-state').innerText(),'Game over');
 await page.getByRole('button',{name:'Previous position'}).click();await idle();
 // Promotion is explicit, including underpromotion.
 await page.locator('#position-input').fill('4k3/P7/8/8/8/8/8/4K3 w - - 0 1');
 await page.getByRole('button',{name:'Load position',exact:true}).click();await idle();
 await page.locator('[data-square="a7"]').click();await page.locator('[data-square="a8"]').click();
 assert.equal(await page.locator('#promotion').isVisible(),true);
 await page.locator('#promotion-piece').selectOption('n');await page.getByRole('button',{name:'Play promotion'}).click();await idle();
 assert.match(await page.locator('[data-square="a8"]').getAttribute('aria-label'),/White knight/);
 // Mobile reflow, raw details and dark appearance.
 await page.getByRole('button',{name:'Try a mate in one'}).click();await idle();
 await page.setViewportSize({width:390,height:844});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
 const square=await page.locator('.square').first().boundingBox();assert.ok(square.width>=43);
 await page.screenshot({path:path.join(out,'chess-tutor-mobile.png'),fullPage:true});
 await page.locator('.model-panel summary').click();
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
 await page.emulateMedia({colorScheme:'dark',reducedMotion:'reduce'});
 await page.screenshot({path:path.join(out,'chess-tutor-mobile-dark.png'),fullPage:true});
 assert.deepEqual(errors,[]);
 const report={status:'passed',checks:['real engine and local CPU model','board click and keyboard selection','board orientation','game navigation','failed navigation preserves board and history index','engine preview attribution','invalid input preserves board','PGN mainline and inert HTML-like headers','fivefold repetition survives game navigation','mate and terminal position','explicit underpromotion','390px reflow and square targets','dark appearance','reduced motion preference','no browser exceptions'],screenshots:['chess-tutor-desktop.png','chess-tutor-mobile.png','chess-tutor-mobile-dark.png']};
 fs.writeFileSync(path.join(out,'chess-tutor-browser-qa.json'),JSON.stringify(report,null,2));
 console.log(JSON.stringify(report));await browser.close();
})().catch(error=>{console.error(error);process.exitCode=1});
