"use strict";

function drawContours(canvas, {levels,bounds}, marker, name) {
  const ctx = canvas.getContext("2d");
  const {width,height} = canvas;
  const [[xmin,xmax],[ymin,ymax]] = bounds;
  const scale = Math.min((width-154)/(xmax-xmin),(height-218)/(ymax-ymin));
  const x = (value) => width/2+(value-(xmin+xmax)/2)*scale;
  const y = (value) => 291-(value-(ymin+ymax)/2)*scale;
  const blue = ["#0a356e","#12498f","#1054a8","#175fb5","#1769c1","#2574c7","#2b7bbe","#347dbd"];
  const format = (value) => value.toLocaleString("pt-BR", {
    maximumSignificantDigits:4, notation:Math.abs(value)>=10000 ? "scientific" : "standard",
  });

  ctx.fillStyle = "#edf6fd";
  ctx.fillRect(0,0,width,height);
  ctx.fillStyle = "#14385e";
  ctx.font = "bold 25px system-ui, sans-serif";
  ctx.fillText(name,30,40);
  ctx.font = "17px system-ui, sans-serif";
  ctx.fillText("Cartão " + marker + "  ·  Vista XY",30,65);

  const left = x(xmin), right = x(xmax), top = y(ymax), bottom = y(ymin);
  ctx.fillStyle = "#f8fcff";
  ctx.fillRect(left,top,right-left,bottom-top);
  for (let i = 0; i <= 10; i++) {
    const tickX = xmin+(xmax-xmin)*i/10, tickY = ymin+(ymax-ymin)*i/10;
    ctx.beginPath();
    ctx.moveTo(x(tickX),top);
    ctx.lineTo(x(tickX),bottom);
    ctx.moveTo(left,y(tickY));
    ctx.lineTo(right,y(tickY));
    ctx.strokeStyle = i%5 === 0 ? "#9ab5ce" : "#cbdceb";
    ctx.lineWidth = 1;
    ctx.stroke();
    if (i%2 === 0) {
      ctx.font = "15px system-ui, sans-serif";
      ctx.fillStyle = "#274763";
      ctx.textAlign = "center";
      ctx.fillText(format(tickX),x(tickX),bottom+21);
      ctx.textAlign = "right";
      ctx.fillText(format(tickY),left-9,y(tickY)+5);
    }
  }

  ctx.fillStyle = "#14385e";
  ctx.font = "bold 18px system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText("X",right+24,bottom+22);
  ctx.fillText("Y",left-21,top-13);
  ctx.lineCap = "round";
  for (const [i,level] of levels.entries()) {
    ctx.beginPath();
    ctx.lineWidth = 2.6;
    ctx.strokeStyle = blue[i];
    for (const [a,b] of level.segments) {
      ctx.moveTo(x(a[0]),y(a[1]));
      ctx.lineTo(x(b[0]),y(b[1]));
    }
    ctx.stroke();
  }

  ctx.textAlign = "left";
  ctx.fillStyle = "#14385e";
  ctx.font = "bold 18px system-ui, sans-serif";
  ctx.fillText(levels.length ? "Altura das curvas" : "Altura constante em toda a malha",30,height-91);
  ctx.font = "16px system-ui, sans-serif";
  for (const [i,level] of levels.entries()) {
    const left = 30+i%4*198, baseline = height-59+Math.floor(i/4)*29;
    ctx.beginPath();
    ctx.lineWidth = 3;
    ctx.strokeStyle = blue[i];
    ctx.moveTo(left,baseline-6);
    ctx.lineTo(left+24,baseline-6);
    ctx.stroke();
    ctx.fillText("z = "+format(level.height),left+34,baseline);
  }
}
