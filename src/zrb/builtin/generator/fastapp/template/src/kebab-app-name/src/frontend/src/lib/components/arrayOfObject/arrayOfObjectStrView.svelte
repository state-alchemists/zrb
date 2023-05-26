<script lang="ts">
    export let data: any[] = [];
    export let captionKey: string = '';
    export let separator: string = ', '

    function dataToStr(data: any[]) {
        data.map((row) => rowToStr(row)).join(separator)
    }

    function rowToStr(row: any): string {
        if (captionKey == '') {
            return JSON.stringify(row)
        }
        return row[captionKey];
    }
</script>
{dataToStr(data)}