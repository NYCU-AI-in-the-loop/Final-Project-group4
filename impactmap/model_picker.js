export default function(component) {
    const { data, parentElement, setStateValue } = component;
    const select = parentElement.querySelector('select');
    select.replaceChildren();
    if (!data.selected) {
        const placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = 'Missing API key';
        placeholder.disabled = true;
        select.appendChild(placeholder);
    }
    for (const item of data.options) {
        const option = document.createElement('option');
        option.value = item.value;
        option.textContent = item.label;
        option.disabled = item.disabled;
        select.appendChild(option);
    }
    select.value = data.selected || '';
    select.disabled = data.disabled;
    select.onchange = () => {
        const option = select.selectedOptions[0];
        if (!select.disabled && option && !option.disabled) {
            setStateValue('provider', select.value);
        }
    };
    return () => { select.onchange = null; };
}
