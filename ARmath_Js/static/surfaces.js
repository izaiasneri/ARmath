"use strict";

const surfaces = (() => {
  const {sin, cos, hypot, exp, PI} = Math;
  const catalog = [
    ["Paraboloide elíptico", "z=2x^{2}+2y^{2}", (x,y) => 2*x*x+2*y*y],
    ["Paraboloide hiperbólico (sela)", "z=2x^{2}-2y^{2}", (x,y) => 2*x*x-2*y*y],
    ["Ondas senoidais", "z=\\sin(2x)\\cos(2y)", (x,y) => sin(2*x)*cos(2*y)],
    ["Elipsoide", "\\frac{x^{2}}{0{,}9^{2}}+\\frac{y^{2}}{0{,}7^{2}}+\\frac{z^{2}}{0{,}5^{2}}=1", (u,v) => [.9*cos(u)*sin(v),.7*sin(u)*sin(v),.5*cos(v)], 0, PI],
    ["Toro", "{(\\sqrt{x^{2}+y^{2}}-0{,}65)}^{2}+z^{2}=0{,}25^{2}", (u,v) => {
      const r = .65+.25*cos(v);
      return [r*cos(u),r*sin(u),.25*sin(v)];
    }, 0, 2*PI],
    ["Hiperboloide de uma folha", "x^{2}+y^{2}-z^{2}=0{,}45^{2}", (u,z) => [hypot(.45,z)*cos(u),hypot(.45,z)*sin(u),z], -.75, .75],
    ["Cone duplo", "x^{2}+y^{2}=z^{2}", (u,z) => [Math.abs(z)*cos(u),Math.abs(z)*sin(u),z], -.85, .85],
    ["Superfície gaussiana", "z=e^{-3(x^{2}+y^{2})}", (x,y) => exp(-3*(x*x+y*y))],
    ["Ondulações concêntricas", "z=\\cos(6\\sqrt{x^{2}+y^{2}})", (x,y) => cos(6*hypot(x,y))],
    ["Função personalizada"],
  ];
  const sequence = (size, min, max) => Array.from({length:size}, (_, i) => min+(max-min)*i/(size-1));
  const operate = {
    "+": (a,b) => a+b, "-": (a,b) => a-b, "*": (a,b) => a*b,
    "/": (a,b) => a/b, "^": (a,b) => a**b,
  };
  const functions = new Map(["sin","cos","tan","exp","sqrt","log","abs"].map((name) => [name, Math[name]]));
  const term = (evaluate, latex) => Object.assign(evaluate, {latex});

  // Recursive descent keeps the accepted grammar independent of JavaScript syntax.
  function compile(expression) {
    if (!expression || expression.length > 120) throw new Error("Digite uma expressão de até 120 caracteres.");
    const invalid = () => new Error("Use x, y, pi, e, operações aritméticas e funções como sin, cos ou sqrt.");
    const tokens = expression.match(/(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|[a-z]+|\*\*|[^\s]/g) || [];
    let i = 0;
    const take = (token) => tokens[i] === token && ++i;
    function group() {
      if (!take("(")) throw invalid();
      const value = additive();
      if (!take(")")) throw invalid();
      return value;
    }
    function atom() {
      if (tokens[i] === "(") {
        const value = group();
        return term((x,y) => value(x,y), "(" + value.latex + ")");
      }
      const token = tokens[i++];
      if (token === "x") return term((x) => x, "x");
      if (token === "y") return term((_,y) => y, "y");
      if (token === "pi") return term(() => PI, "\\pi");
      if (token === "e") return term(() => Math.E, "e");
      if (token && /^(?:\d|\.\d)/.test(token)) {
        const [mantissa, exponent] = token.split(/[eE]/);
        const latex = exponent === undefined ? token : "{" + mantissa + "\\times 10^{" + exponent + "}}";
        return term(() => finite(Number(token)), latex);
      }
      if (!functions.has(token)) throw invalid();
      const arg = group(), fn = functions.get(token);
      const latex = {
        sqrt: "\\sqrt{" + arg.latex + "}",
        exp: "e^{" + arg.latex + "}",
        abs: "| " + arg.latex + " |",
      }[token] ?? "\\" + token + "(" + arg.latex + ")";
      return term((x,y) => finite(fn(arg(x,y))), latex);
    }
    function unary() {
      if (tokens[i] === "+" || tokens[i] === "-") {
        const sign = tokens[i++];
        const operand = unary();
        return term((x,y) => sign === "-" ? -operand(x,y) : operand(x,y), sign + operand.latex);
      }
      const base = atom();
      if (!take("^") && !take("**")) return base;
      const power = unary();
      return term((x,y) => finite(base(x,y)**power(x,y)), "{" + base.latex + "}^{" + power.latex + "}");
    }
    function combine(next, operators) {
      let value = next();
      while (operators.includes(tokens[i])) {
        const symbol = tokens[i++], op = operate[symbol], left = value, right = next();
        const latex = symbol === "/" ? "\\frac{" + left.latex + "}{" + right.latex + "}"
          : left.latex + (symbol === "*" ? "\\cdot " : symbol) + right.latex;
        value = term((x,y) => finite(op(left(x,y),right(x,y))), latex);
      }
      return value;
    }
    const additive = () => combine(() => combine(unary, ["*","/"]), ["+","-"]);
    const evaluate = additive();
    if (i !== tokens.length) throw invalid();
    return evaluate;
  }

  function finite(value) {
    if (!Number.isFinite(value)) throw new Error("A função deve ter valores reais e finitos na malha.");
    return value;
  }

  function referenceTicks([min,max], unit) {
    let low = min/unit, high = max/unit;
    if (!Number.isFinite(low)) low = Math.sign(low)*Number.MAX_VALUE;
    if (!Number.isFinite(high)) high = Math.sign(high)*Number.MAX_VALUE;
    if (Math.max(Math.abs(low),Math.abs(high)) > 1e306) return [low,high];
    if (low === high) {
      low -= .05;
      high += .05;
    }
    const target = Math.max(high-low,.1)/4;
    const magnitude = 10**Math.floor(Math.log10(target));
    const step = [1,2,2.5,5,10].map((factor) => factor*magnitude).find((size) => size >= target) ?? 10*magnitude;
    const start = Math.floor(low/step), end = Math.ceil(high/step);
    return Array.from({length:end-start+1}, (_, i) => (start+i)*step);
  }

  function geometry(rows, units) {
    const triangles = [];
    for (let y = 1; y < rows.length; y++) {
      for (let x = 1; x < rows[y].length; x++) {
        const a = rows[y-1][x-1], b = rows[y-1][x], c = rows[y][x-1], d = rows[y][x];
        triangles.push([a,b,d],[a,d,c]);
      }
    }
    const points = rows.flat();
    const bounds = units.map((_, i) => {
      const coordinates = points.map((point) => point[i]);
      return [Math.min(...coordinates), Math.max(...coordinates)];
    });
    return {triangles, bounds, units};
  }

  const predefined = catalog.slice(0,9).map(([, , fn, start, end]) => {
    if (start !== undefined) {
      const angles = sequence(29,0,2*PI);
      return geometry(sequence(19,start,end).map((v) => angles.map((u) => fn(u,v))), [1,1,1]);
    }
    const values = sequence(17,-1,1);
    return geometry(values.map((y) => values.map((x) => [x,y,.65*fn(x,y)])), [1,1,.65]);
  });

  function custom(expression) {
    const fn = compile(expression);
    const values = sequence(25,-5,5);
    const rows = values.map((y) => values.map((x) => [x,y,fn(x,y)]));
    const heights = rows.flat().map((point) => Math.abs(point[2]));
    if (!heights.every(Number.isFinite)) throw new Error("A função deve ter valores reais e finitos na malha.");
    const units = [.2,.2,.65/Math.max(5,...heights)];
    return {
      ...geometry(rows.map((row) => row.map((p) => p.map((value,i) => value*units[i]))), units),
      latex: "f(x,y)=" + fn.latex,
    };
  }

  function rotate([x,y,z], angles) {
    const [a,b,c] = angles;
    [y,z] = [cos(a)*y-sin(a)*z,sin(a)*y+cos(a)*z];
    [x,z] = [cos(b)*x+sin(b)*z,-sin(b)*x+cos(b)*z];
    return [cos(c)*x-sin(c)*y,sin(c)*x+cos(c)*y,z];
  }

  function splitFace(vertices, axis, nearSide, order, emit) {
    if (axis === 3) {
      emit(vertices,order);
      return;
    }
    const distances = vertices.map(({point}) => Math.abs(point[axis]) < 1e-9 ? 0 : point[axis]*nearSide[axis]);
    const first = order*3;
    if (distances.every((d) => d === 0)) {
      emit(vertices,(first+1)*3**(2-axis));
      return;
    }
    if (distances.every((d) => d <= 0)) {
      splitFace(vertices,axis+1,nearSide,first,emit);
      return;
    }
    if (distances.every((d) => d >= 0)) {
      splitFace(vertices,axis+1,nearSide,first+2,emit);
      return;
    }

    const far = [], near = [];
    for (const [i, vertex] of vertices.entries()) {
      const j = (i+1)%vertices.length;
      const a = distances[i], b = distances[j];
      if (a <= 0) far.push(vertex);
      if (a >= 0) near.push(vertex);
      if (a*b < 0) {
        const next = vertices[j];
        const point = vertex.point.map((value,k) => value+(next.point[k]-value)*a/(a-b));
        point[axis] = 0;
        const intersection = {point,edges:vertex.edges & next.edges};
        far.push(intersection);
        near.push(intersection);
      }
    }
    splitFace(far,axis+1,nearSide,first,emit);
    splitFace(near,axis+1,nearSide,first+2,emit);
  }

  function draw(ctx, markers, options, customGeometry) {
    const faces = [], markerLayers = [], guides = [], intersections = [], sections = [], labels = [];
    const angles = options.angles.map((angle) => angle*PI/180);
    let coordinate;
    for (const {id,corners} of markers) {
      const mesh = id === 9 ? customGeometry : predefined[id];
      const project = vision.projector(corners,ctx.canvas.width,ctx.canvas.height);
      const map = (point) => project(rotate(point,angles).map((value) => value*options.scale));
      const projected = new Map();
      const cached = (p) => {
        if (!projected.has(p)) projected.set(p,map(p));
        return projected.get(p);
      };
      const markerFaces = options.planes ? [] : faces;
      let nearSide;
      if (options.planes) {
        const origin = map([0,0,0]);
        const axes = [[.1,0,0],[0,.1,0],[0,0,.1]].map(map);
        // Screen-space winding tells which side of each plane faces the camera.
        nearSide = axes.map((_,axis) => {
          const u = axes[(axis+1)%3], v = axes[(axis+2)%3];
          if (!origin || !u || !v) return 1;
          const winding = (u[0]-origin[0])*(v[1]-origin[1])-(u[1]-origin[1])*(v[0]-origin[0]);
          return winding < 0 ? 1 : -1;
        });
        markerLayers.push({faces:markerFaces,depth:origin?.[2] ?? Infinity});
      }
      const axis = {xy:2,xz:1,yz:0}[options.plane];
      const slicing = axis !== undefined;
      const level = slicing ? Math.abs(options.offset)*mesh.bounds[axis][Number(options.offset >= 0)] : 0;
      if (slicing && coordinate === undefined) {
        const number = (level/mesh.units[axis]).toLocaleString("pt-BR",{maximumSignificantDigits:4});
        coordinate = "xyz"[axis]+" = "+number;
      }
      function face(vertices, color, stroke, lineWidth) {
        function enqueue(points, order, edges) {
          if (!points.every(Boolean)) return;
          const depth = points.reduce((sum,p) => sum+p[2],0)/points.length;
          markerFaces.push({points,depth,color,stroke,lineWidth,order,edges});
        }
        if (!nearSide) {
          enqueue(vertices.map(cached),0);
          return;
        }
        // Preserve only original mesh edges when a face is clipped at a plane.
        const polygon = vertices.map((point,i) => ({
          point, edges: (1 << i) | (1 << ((i+vertices.length-1)%vertices.length)),
        }));
        splitFace(polygon,0,nearSide,0,(piece,order) => {
          const edges = stroke && piece.map(({edges},i) => edges & piece[(i+1)%piece.length].edges);
          enqueue(piece.map(({point}) => cached(point)),order,edges);
        });
      }
      for (const triangle of mesh.triangles) {
        const height = triangle.reduce((sum,p) => sum+p[2],0)/3;
        face(triangle, `hsl(216, 76%, ${27+Math.max(-1,Math.min(2,height))*7}%)`,
          "rgba(55,179,255,.75)", .55);
        if (!slicing) continue;
        const distances = triangle.map((p) => Math.abs(p[axis]-level) < 1e-9 ? 0 : p[axis]-level);
        if (distances.every((d) => d === 0)) continue;
        const hits = [];
        for (let i = 0; i < 3; i++) {
          const j = (i+1)%3, d = distances[i], e = distances[j];
          if (d === 0) hits.push(triangle[i]);
          if (d*e < 0) hits.push(triangle[i].map((p,k) => p+(triangle[j][k]-p)*d/(d-e)));
        }
        if (hits.length === 2) sections.push(hits.map(map));
      }
      function drawPlane(axis, level, uTicks, vTicks, color, stroke, width) {
        const u = (axis+1)%3, v = (axis+2)%3;
        const grid = uTicks.map((a) => vTicks.map((b) => {
          const point = [0,0,0];
          point[axis] = level;
          point[u] = a;
          point[v] = b;
          return point;
        }));
        for (let i = 1; i < uTicks.length; i++) {
          for (let j = 1; j < vTicks.length; j++) {
            face([grid[i-1][j-1],grid[i][j-1],grid[i][j],grid[i-1][j]],color,stroke,width);
          }
        }
      }
      if (slicing) {
        const tangents = [0,1,2].filter((i) => i !== axis);
        const extent = Math.max(1.2,...tangents.flatMap((i) => mesh.bounds[i].map(Math.abs)))*1.12;
        const ticks = sequence(17,-extent,extent);
        drawPlane(axis,level,ticks,ticks,"rgba(223,37,52,.48)","rgba(255,231,81,.92)",.65);
      }

      if (options.planes) {
        const extents = mesh.bounds.map(([min,max]) => Math.max(Math.abs(min),Math.abs(max)));
        const minimum = .35*Math.max(...extents);
        const colors = ["rgba(48,211,127,.50)", "rgba(244,75,87,.50)", "rgba(255,217,58,.50)"];
        const sharedExtents = [Infinity,Infinity,Infinity];
        for (const [axis,color] of colors.entries()) {
          const u = (axis+1)%3, v = (axis+2)%3;
          const step = 1.15*Math.max(extents[u],extents[v],minimum)/7;
          const ticks = (i) => {
            const cells = Math.ceil(1.15*Math.max(extents[i],minimum)/step-1e-9);
            return sequence(2*cells+1,-cells,cells).map((n) => n*step);
          };
          const uTicks = ticks(u), vTicks = ticks(v);
          drawPlane(axis,0,uTicks,vTicks,color,"rgba(174,179,186,.76)",.65);
          sharedExtents[u] = Math.min(sharedExtents[u],uTicks.at(-1));
          sharedExtents[v] = Math.min(sharedExtents[v],vTicks.at(-1));
        }
        for (const [axis,extent] of sharedExtents.entries()) {
          const start = [0,0,0], end = [0,0,0];
          start[axis] = -extent;
          end[axis] = extent;
          intersections.push([map(start),map(end)]);
        }
      }

      const bounds = mesh.bounds.map(([min,max]) => [Math.min(min,0),Math.max(max,0)]);
      for (let axis = 0; axis < 3; axis++) {
        const [u,v] = [0,1,2].filter((i) => i !== axis);
        const line = (along, from, to, color, dashed = false) => {
          const a = along.slice(), b = along.slice();
          a[axis] = from;
          b[axis] = to;
          guides.push({points:[map(a),map(b)],color,dashed});
        };
        const [min,max] = bounds[axis];
        if (options.axes) {
          const end = Math.max(1.2,max+.14), color = ["#ff777f","#73ffa8","#79c4ff"][axis];
          line([0,0,0],min,end,color);
          const p = [0,0,0];
          p[axis] = end;
          labels.push({point:map(p),text:"XYZ"[axis],color});
        }
        if (options.box) {
          for (const a of mesh.bounds[u]) for (const b of mesh.bounds[v]) {
            const p = [0,0,0];
            p[u] = a;
            p[v] = b;
            line(p,...mesh.bounds[axis],"#e1ebfa");
          }
        }
      }
      if (options.grid) {
        const ticks = mesh.bounds.map((range,i) => referenceTicks(range,mesh.units[i]));
        const clearance = .25*Math.max(...mesh.bounds.map(([min,max]) => max-min));
        const lower = mesh.bounds.map(([min]) => min-clearance);
        const upper = mesh.bounds.map(([,max]) => max+clearance);
        const colors = ["rgba(235,56,65,.45)", "rgba(255,215,60,.45)", "rgba(53,146,255,.45)"];
        for (let axis = 0; axis < 3; axis++) {
          const u = (axis+1)%3, v = (axis+2)%3;
          const corners = [[lower[u],lower[v]], [upper[u],lower[v]], [upper[u],upper[v]], [lower[u],upper[v]]];
          face(corners.map(([a,b]) => {
            const point = lower.slice();
            point[u] = a;
            point[v] = b;
            return point;
          }), colors[axis]);
          for (const [a,b] of corners) {
            const start = lower.slice(), end = upper.slice();
            start[u] = end[u] = a;
            start[v] = end[v] = b;
            guides.push({points:[map(start),map(end)],color:"rgba(234,245,255,.38)"});
          }
          for (const tick of ticks[axis]) {
            const coordinate = tick*mesh.units[axis];
            if (coordinate < lower[axis] || coordinate > upper[axis]) continue;
            const start = lower.slice();
            start[axis] = coordinate;
            for (const across of [u,v]) {
              const end = start.slice();
              end[across] = upper[across];
              guides.push({points:[map(start),map(end)],color:"rgba(234,245,255,.72)",dashed:true});
              if (across === u) labels.push({
                point:map(end), text:tick.toLocaleString("pt-BR",{maximumSignificantDigits:3}), color:"#fff",
              });
            }
          }
        }
      }
    }
    function path(points) {
      if (!points.every(Boolean)) return false;
      ctx.beginPath();
      points.forEach(([x,y], i) => i ? ctx.lineTo(x,y) : ctx.moveTo(x,y));
      return true;
    }
    ctx.save();
    const byDepth = (a,b) => b.depth-a.depth;
    const ordered = options.planes
      ? markerLayers.sort(byDepth).flatMap(({faces}) => faces.sort((a,b) => a.order-b.order || byDepth(a,b)))
      : faces.sort(byDepth);
    for (const {points,color,stroke,lineWidth,edges} of ordered) {
      path(points);
      ctx.closePath();
      ctx.fillStyle = color;
      ctx.fill();
      if (stroke) {
        ctx.lineWidth = lineWidth;
        ctx.strokeStyle = stroke;
        if (edges && !edges.every(Boolean)) {
          ctx.beginPath();
          for (const [i, drawEdge] of edges.entries()) {
            if (!drawEdge) continue;
            const [x,y] = points[i], [endX,endY] = points[(i+1)%points.length];
            ctx.moveTo(x,y);
            ctx.lineTo(endX,endY);
          }
        }
        ctx.stroke();
      }
    }
    for (const {points,color,dashed} of guides) {
      if (!path(points)) continue;
      ctx.setLineDash(dashed ? [4,4] : []);
      ctx.lineWidth = dashed ? 1 : 1.6;
      ctx.strokeStyle = color;
      ctx.stroke();
    }
    ctx.setLineDash([]);
    ctx.strokeStyle = "white";
    ctx.lineWidth = 1.8;
    for (const points of intersections) if (path(points)) ctx.stroke();
    ctx.lineWidth = 2.4;
    for (const points of sections) if (path(points)) ctx.stroke();
    ctx.font = "bold 15px system-ui";
    for (const {point,text,color} of labels) {
      if (!point) continue;
      ctx.strokeStyle = "#172137";
      ctx.strokeText(text,point[0]+3,point[1]-3);
      ctx.fillStyle = color;
      ctx.fillText(text,point[0]+3,point[1]-3);
    }
    ctx.restore();
    return coordinate;
  }

  return {catalog, custom, draw};
})();
