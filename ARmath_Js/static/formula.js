"use strict";

// Compile the LaTeX emitted by the expression parser into native MathML.
function renderFormula(latex) {
  const tokens = latex.match(/\\[a-z]+|\d+(?:\.\d*)?|\.\d+|[^\s]/g);
  const namespace = "http://www.w3.org/1998/Math/MathML";
  const element = (name, ...children) => {
    const node = document.createElementNS(namespace, name);
    node.append(...children);
    return node;
  };
  let index = 0;

  function group() {
    index++;
    const content = row();
    index++;
    return content;
  }

  function atom() {
    if (tokens[index] === "{") return group();
    const token = tokens[index++];
    switch (token) {
      case "\\frac": return element("mfrac", group(), group());
      case "\\sqrt": return element("msqrt", group());
      case "\\sin":
      case "\\cos":
      case "\\tan":
      case "\\log":
        return element("mi", token.slice(1));
      case "\\pi": return element("mi", "π");
      case "\\times": return element("mo", "×");
      case "\\cdot": return element("mo", "⋅");
      case "-": return element("mo", "−");
      default:
        if (/^[\d.]/.test(token)) return element("mn", token);
        return element(/^[a-z]$/.test(token) ? "mi" : "mo", token);
    }
  }

  function row() {
    const parts = [];
    while (index < tokens.length && tokens[index] !== "}") {
      let part = atom();
      if (tokens[index] === "^") {
        index++;
        part = element("msup", part, group());
      }
      parts.push(part);
    }
    return element("mrow", ...parts);
  }

  const annotation = element("annotation", latex);
  annotation.setAttribute("encoding", "application/x-tex");
  const math = element("math", element("semantics", row(), annotation));
  math.setAttribute("display", "block");
  return math;
}
