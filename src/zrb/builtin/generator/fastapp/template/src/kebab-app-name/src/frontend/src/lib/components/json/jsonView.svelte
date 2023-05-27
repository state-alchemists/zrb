<script lang="ts">
    export let data: any;

    function dataToStr(data: any): string {
        try {
            return JSON.stringify(data, null, 2);
        } catch(error) {
            return data + '';
        }
    }
</script>
<pre {...$$restProps}>{dataToStr(data)}</pre>
