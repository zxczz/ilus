"""GATK modules

Author: Shujia Huang
Date: 2020-04-19 15:19:56
"""
import os


def markduplicates(config, input_bam, output_markdup_bam, out_metrics_fname):
    gatk = config["gatk"]["gatk"]
    java_options = "--java-options \"%s\"" % " ".join(config["gatk"]["markdup_java_options"]) \
        if "markdup_java_options" in config["gatk"] \
           and len(config["gatk"]["markdup_java_options"]) else ""

    return ("time {gatk} {java_options} MarkDuplicates "
            "-I {input_bam} "
            "-M {out_metrics_fname} "
            "-O {output_markdup_bam}").format(**locals())


def baserecalibrator(config, input_bam, output_bqsr_bam, out_bqsr_recal_table):
    gatk = config["gatk"]["gatk"]
    java_options = "--java-options \"%s\"" % " ".join(config["gatk"]["bqsr_java_options"]) \
        if "bqsr_java_options" in config["gatk"] \
           and len(config["gatk"]["bqsr_java_options"]) else ""

    reference = config["resources"]["reference"]  # reference fasta
    known_site_1000G_indel = config["gatk"]["bundle"]["1000G_known_indel"]
    known_site_mills_gold_indels = config["gatk"]["bundle"]["mills"]
    known_site_dbsnp = config["gatk"]["bundle"]["dbsnp"]

    # create recalibrate table file for BQSR
    recal_data_cmd = ("time {gatk} {java_options} BaseRecalibrator "
                      "-R {reference} "
                      "--known-sites {known_site_1000G_indel} "
                      "--known-sites {known_site_mills_gold_indels} "
                      "--known-sites {known_site_dbsnp} "
                      "-I {input_bam} "
                      "-O {out_bqsr_recal_table}").format(**locals())

    # ApplyBQSR
    apply_bqsr_cmd = ("time {gatk} {java_options} ApplyBQSR "
                      "-R {reference} "
                      "--bqsr-recal-file {out_bqsr_recal_table} "
                      "-I {input_bam} "
                      "-O {output_bqsr_bam}").format(**locals())

    return recal_data_cmd + " && " + apply_bqsr_cmd


def haplotypecaller_gvcf(config, input_bam, output_gvcf_fname, interval=None):
    gatk = config["gatk"]["gatk"]
    java_options = "--java-options \"%s\"" % " ".join(config["gatk"]["hc_gvcf_java_options"]) \
        if "hc_gvcf_java_options" in config["gatk"] \
           and len(config["gatk"]["hc_gvcf_java_options"]) else ""

    reference = config["resources"]["reference"]  # reference fasta
    cmd = ("time {gatk} {java_options} HaplotypeCaller "
           "-R {reference} "
           "--emit-ref-confidence GVCF "
           "-I {input_bam} "
           "-O {output_gvcf_fname}").format(**locals())

    if interval:
        cmd += " -L %s" % interval

    return cmd


def genotypegvcfs(config, input_sample_gvcfs, output_vcf_fname, interval=None):
    """
    :param config:
    :param input_sample_gvcfs:
    :param output_vcf_fname:
    :param interval: A list like
    :return:
    """
    interval_str = ""
    if interval:
        if len(interval) == 1:
            interval_str = interval[0]
        elif len(interval) == 2:
            interval_str = ":".join(interval)
        else:
            interval_str = "%s:%s-%s" % (interval[0], interval[1], interval[2])

    gatk = config["gatk"]["gatk"]
    java_options = "--java-options \"%s\"" % " ".join(config["gatk"]["genotype_java_options"]) \
        if "genotype_java_options" in config["gatk"] \
           and len(config["gatk"]["genotype_java_options"]) else ""

    genomicsDBImport_options = "%s" % " ".join(config["gatk"]["genomicsDBImport_options"]) \
        if "genomicsDBImport_options" in config["gatk"] else ""

    reference = config["resources"]["reference"]  # reference fasta

    # create a combine gvcf
    directory, fname = os.path.split(output_vcf_fname)

    # The prefix of file name of combine gvcf set to be the same with input ``fname``
    combine_gvcf_fname = os.path.join(directory, fname.replace(".vcf", ".g.vcf"))

    genotype_cmd = []
    gvcfs = " ".join(["-V %s" % s for s in input_sample_gvcfs])
    is_gDBI = False
    if len(input_sample_gvcfs) > 2:
        # use GenomicsDBImport
        combine_gvcf_fname = combine_gvcf_fname.split(".g.vcf")[0] + ".gvcfs_db"
        is_gDBI = True
        genomicsDBImport_cmd = ("rm -rf {combine_gvcf_fname} && "
                                "time {gatk} {java_options} GenomicsDBImport {genomicsDBImport_options} "
                                "-R {reference} {gvcfs} "
                                "--genomicsdb-workspace-path {combine_gvcf_fname}").format(**locals())

        if interval:
            genomicsDBImport_cmd += " -L %s" % interval_str

        genotype_cmd = [genomicsDBImport_cmd]

    elif len(input_sample_gvcfs) > 1:
        combine_gvcf_cmd = ("time {gatk} {java_options} CombineGVCFs "
                            "-R {reference} {gvcfs} "
                            "-O {combine_gvcf_fname}").format(**locals())

        if interval:
            combine_gvcf_cmd += " -L %s" % interval_str

        genotype_cmd = [combine_gvcf_cmd]
    else:
        combine_gvcf_fname = input_sample_gvcfs[0]

    if is_gDBI:
        genotype_cmd.append(("time {gatk} {java_options} GenotypeGVCFs "
                             "-R {reference} "
                             "-V gendb://{combine_gvcf_fname} "
                             "-O {output_vcf_fname}").format(**locals()))
    else:
        genotype_cmd.append(("time {gatk} {java_options} GenotypeGVCFs "
                             "-R {reference} "
                             "-V {combine_gvcf_fname} "
                             "-O {output_vcf_fname}").format(**locals()))

    genotype_cmd.append("rm -rf %s %s.tbi" % (combine_gvcf_fname, combine_gvcf_fname))
    return " && ".join(genotype_cmd)


def variantrecalibrator(config, input_vcf, output_vcf_fname):
    gatk = config["gatk"]["gatk"]
    java_options = "--java-options \"%s\"" % " ".join(config["gatk"]["vqsr_java_options"]) \
        if "vqsr_java_options" in config["gatk"] \
           and len(config["gatk"]["vqsr_java_options"]) else ""

    vqsr_options = " ".join(config["gatk"]["vqsr_options"]) if "vqsr_options" in config["gatk"] else ""

    reference = config["resources"]["reference"]  # reference fasta

    # Set name
    out_prefix = output_vcf_fname.replace(".gz", "").replace(".vcf", "")  # delete .vcf.gz
    out_snp_vqsr_fname = out_prefix + ".SNPs.vcf.gz"

    resource_hapmap = config["gatk"]["bundle"]["hapmap"]
    resource_omni = config["gatk"]["bundle"]["mills"]
    resource_1000G = config["gatk"]["bundle"]["1000G"]
    resource_dbsnp = config["gatk"]["bundle"]["dbsnp"]
    resource_mills_gold_indels = config["gatk"]["bundle"]["mills"]

    # SNP VQSR
    snp_vqsr_cmd = ("time {gatk} {java_options} VariantRecalibrator "
                    "-R {reference} "
                    "-V {input_vcf} "
                    "--resource:hapmap,known=false,training=true,truth=true,prior=15.0 {resource_hapmap} "
                    "--resource:omini,known=false,training=true,truth=false,prior=12.0 {resource_omni} "
                    "--resource:1000G,known=false,training=true,truth=false,prior=10.0 {resource_1000G} "
                    "--resource:dbsnp,known=true,training=false,truth=false,prior=2.0 {resource_dbsnp} "
                    "{vqsr_options} "
                    "-mode SNP "
                    "--tranches-file {out_prefix}.SNPs.tranches "
                    "-O {out_prefix}.SNPs.recal").format(**locals())

    apply_snp_vqsr_cmd = ("time {gatk} {java_options} ApplyVQSR "
                          "-R {reference} "
                          "-V {input_vcf} "
                          "--tranches-file {out_prefix}.SNPs.tranches "
                          "--recal-file {out_prefix}.SNPs.recal "
                          "--truth-sensitivity-filter-level 99.0 "
                          "-mode SNP "
                          "-O {out_snp_vqsr_fname}").format(**locals())

    # Indel VQSR after SNP
    indel_vqsr_cmd = ("time {gatk} {java_options} VariantRecalibrator "
                      "-R {reference} "
                      "-V {out_snp_vqsr_fname} "
                      "--resource:mills,known=true,training=true,truth=true,prior=12.0 {resource_mills_gold_indels} "
                      "{vqsr_options} "
                      "--tranches-file {out_prefix}.INDELs.tranches "
                      "-mode INDEL "
                      "-O {out_prefix}.INDELs.recal").format(**locals())
    apply_indel_vqsr_cmd = ("time {gatk} {java_options} ApplyVQSR "
                            "-R {reference} "
                            "-V {out_snp_vqsr_fname} "
                            "--truth-sensitivity-filter-level 99.0 "
                            "--tranches-file {out_prefix}.INDELs.tranches "
                            "--recal-file {out_prefix}.INDELs.recal "
                            "-mode INDEL "
                            "-O {output_vcf_fname} && rm -f {out_snp_vqsr_fname}").format(**locals())

    return " && ".join([snp_vqsr_cmd, apply_snp_vqsr_cmd, indel_vqsr_cmd, apply_indel_vqsr_cmd])
