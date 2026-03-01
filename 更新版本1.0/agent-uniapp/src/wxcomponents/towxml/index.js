const md = require('./parse/markdown/index'),
    parse = require('./parse/index')

export const useTowxml = (str,type,option)=>{
    option = option || {};
	type = type || "markdown";
    let result;
    switch (type) {
        case 'markdown':
            result = parse(md(str),option);
        break;
        case 'html':
            result = parse(str,option);
        break;
        default:
            throw new Error('Invalid type, only markdown and html are supported');
        break;
    };
    return result;
};
