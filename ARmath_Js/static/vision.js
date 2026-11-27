"use strict";

const vision = (() => {
  const codes = [
    "1011010100110010", "0000111110011010", "0011001100101101", "1001100101000110",
    "0101010010011110", "0111100111001101", "1001111000101110", "1100010011110010",
    "1111111011011010", "1100111101010110",
  ];
  const cross = (a, b, c) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);

  function quadrilateral(points) {
    points.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
    function half(sequence) {
      const hull = [];
      for (const p of sequence) {
        while (hull.length > 1 && cross(hull.at(-2), hull.at(-1), p) <= 0) hull.pop();
        hull.push(p);
      }
      return hull.slice(0, -1);
    }
    const hull = half(points).concat(half(points.reverse()));
    while (hull.length > 4) {
      const costs = hull.map((p, i) => cross(hull.at(i - 1), p, hull[(i + 1) % hull.length]));
      hull.splice(costs.indexOf(Math.min(...costs)), 1);
    }
    if (hull.length !== 4 || hull.some((p, i) =>
      Math.hypot(p[0] - hull.at(i - 1)[0], p[1] - hull.at(i - 1)[1]) < 20)) return null;
    return hull;
  }

  // Project the unit square to the four image corners in clockwise order.
  function homography([[x0,y0], [x1,y1], [x2,y2], [x3,y3]]) {
    const dx = x0 - x1 + x2 - x3, dy = y0 - y1 + y2 - y3;
    const a = x1 - x2, b = x3 - x2, c = y1 - y2, d = y3 - y2;
    const det = a*d - b*c;
    const g = (dx*d - b*dy) / det, h = (a*dy - dx*c) / det;
    return [x1-x0+g*x1, x3-x0+h*x3, x0, y1-y0+g*y1, y3-y0+h*y3, y0, g, h];
  }

  function decode(image, gray, quad) {
    const [a,b,c,d,e,f,g,h] = homography(quad);
    const samples = [];
    for (let row = 0; row < 6; row++) {
      for (let col = 0; col < 6; col++) {
        let sum = 0;
        for (const dy of [.28,.5,.72]) {
          for (const dx of [.28,.5,.72]) {
            const u = (col+dx)/6, v = (row+dy)/6, w = g*u+h*v+1;
            const x = Math.round((a*u+b*v+c)/w), y = Math.round((d*u+e*v+f)/w);
            sum += gray[y*image.width+x];
          }
        }
        samples.push(sum/9);
      }
    }
    const sorted = [...samples].sort((x,y) => x-y);
    const low = sorted[4], high = sorted[33];
    if (high - low < 45) return null;
    const threshold = (high + low) / 2;
    let bits = [];
    for (const [i, value] of samples.entries()) {
      const row = Math.floor(i/6), col = i%6;
      if (!row || row === 5 || !col || col === 5) {
        if (value > threshold) return null;
      } else bits.push(Number(value > threshold));
    }
    for (let turn = 0; turn < 4; turn++) {
      const id = codes.indexOf(bits.join(""));
      if (id !== -1) return {id, corners: [...quad.slice(turn), ...quad.slice(0, turn)]};
      bits = bits.map((_, i) => bits[(i%4)*4 + 3-Math.floor(i/4)]);
    }
    return null;
  }

  function detect(image) {
    const {width, height, data} = image;
    const gray = new Uint8Array(width*height);
    const stride = width+1, integral = new Int32Array(stride*(height+1));
    for (let y = 0; y < height; y++) {
      let sum = 0;
      for (let x = 0; x < width; x++) {
        const i = y*width+x, j = y*stride+x+1;
        gray[i] = (77*data[4*i]+150*data[4*i+1]+29*data[4*i+2]) >> 8;
        sum += gray[i];
        integral[j+stride] = integral[j]+sum;
      }
    }
    const markers = new Map(), queue = new Int32Array(gray.length);
    // Multiple window sizes keep the black perimeter connected at different distances.
    for (const radius of [18, 38, 70]) {
      const mask = new Uint8Array(gray.length);
      for (let y = 0; y < height; y++) {
        const top = Math.max(0,y-radius), bottom = Math.min(height,y+radius+1);
        for (let x = 0; x < width; x++) {
          const l = Math.max(0,x-radius), r = Math.min(width,x+radius+1);
          const sum = integral[bottom*stride+r]-integral[bottom*stride+l]-
            integral[top*stride+r]+integral[top*stride+l];
          if (gray[y*width+x]+9 < sum/((bottom-top)*(r-l))) mask[y*width+x] = 1;
        }
      }
      for (let i = 0; i < mask.length; i++) {
        if (mask[i] !== 1) continue;
        let size = 1, touchesEdge = false;
        const points = [];
        mask[i] = 2;
        queue[0] = i;
        for (let j = 0; j < size; j++) {
          const p = queue[j], x = p%width, y = Math.floor(p/width);
          if (!x || x === width-1 || !y || y === height-1) touchesEdge = true;
          const left = x ? p-1 : -1, right = x < width-1 ? p+1 : -1;
          const up = p-width, down = p+width;
          if (!mask[left] || !mask[right] || !mask[up] || !mask[down]) points.push([x,y]);
          for (const n of [left,right,up,down]) {
            if (mask[n] === 1) {
              mask[n] = 2;
              queue[size++] = n;
            }
          }
        }
        if (touchesEdge || size < 90 || points.length < 4) continue;
        const quad = quadrilateral(points);
        const marker = quad && decode(image, gray, quad);
        if (marker && !markers.has(marker.id)) markers.set(marker.id, marker);
      }
    }
    const area = ({corners}) => corners.reduce((sum, [x,y], i) =>
      sum+x*corners.at(i-1)[1]-y*corners.at(i-1)[0], 0);
    return [...markers.values()].sort((a,b) => Math.abs(area(b))-Math.abs(area(a)));
  }

  function createTracker() {
    const tracks = new Map();
    const holdTime = 160;
    const median = (a, b, c) => Math.max(Math.min(a,b), Math.min(Math.max(a,b),c));

    function update(detections, now) {
      for (const [id, track] of tracks) {
        if (now - track.seenAt > holdTime) tracks.delete(id);
      }
      const visible = new Set();
      const markers = detections.map(({id,corners}) => {
        visible.add(id);
        let track = tracks.get(id);
        if (!track) {
          track = {corners, samples: [corners,corners], seenAt: now};
          tracks.set(id, track);
          return {id,corners};
        }

        // Three samples reject a single bad corner before smoothing the pose.
        const [older,previous] = track.samples;
        const filtered = corners.map((point,i) =>
          point.map((value,j) => median(older[i][j],previous[i][j],value)));
        const distances = track.corners.map(([x,y],i) =>
          Math.hypot(filtered[i][0]-x,filtered[i][1]-y));
        const [a,b,c,d] = track.corners;
        const side = (Math.hypot(a[0]-c[0],a[1]-c[1])+Math.hypot(b[0]-d[0],b[1]-d[1]))/Math.SQRT2/2;
        // A sustained move gets a faster response than small detection jitter.
        const amount = Math.min(.85, .22+5*Math.max(...distances)/Math.max(side,1));
        track.corners = track.corners.map((point,i) =>
          point.map((value,j) => value+amount*(filtered[i][j]-value)));
        track.samples = [previous,corners];
        track.seenAt = now;
        return {id,corners: track.corners};
      });
      for (const [id, track] of tracks) {
        if (!visible.has(id)) markers.push({id,corners: track.corners});
      }
      return markers;
    }

    return {update, reset: () => tracks.clear()};
  }

  function projector(corners, width, height) {
    const [a,b,c,d,e,f,g,h] = homography(corners);
    const cx = width/2, cy = height/2, focal = Math.max(width,height);
    const camera = (x,y,z) => [(x-cx*z)/focal, (y-cy*z)/focal, z];
    const u = camera(a,d,g), v = camera(b,e,h), t = camera(c,f,1);
    const norm = (p) => Math.hypot(...p);
    const length = (norm(u)+norm(v))/2;
    const normal = [
      u[2]*v[1]-u[1]*v[2], u[0]*v[2]-u[2]*v[0], u[1]*v[0]-u[0]*v[1],
    ];
    const zAxis = normal.map((component) => component*length/norm(normal));
    return ([x,y,z]) => {
      const depth = t[2]+u[2]*(x+1)/2+v[2]*(1-y)/2+zAxis[2]*z/2;
      if (depth <= .001) return null;
      return [
        cx+focal*(t[0]+u[0]*(x+1)/2+v[0]*(1-y)/2+zAxis[0]*z/2)/depth,
        cy+focal*(t[1]+u[1]*(x+1)/2+v[1]*(1-y)/2+zAxis[1]*z/2)/depth,
        depth,
      ];
    };
  }

  return {detect, createTracker, projector};
})();
